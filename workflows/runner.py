# -*- coding: utf-8 -*-
"""RunManager：工作流执行器（运行模型见 ARCHITECTURE.md §3.4；M5 kind 泛化见 §5.1/§5.2）。

Run 状态机：running → waiting_human → running → done | failed
- start()   建 run 记录（kind='publish'|'update'）+ 后台线程跑对应图
- get()     run 详情（结果 + 人工任务载荷 + checkpoint 实时进度）
- resume()  人在前端完成平台侧操作后恢复挂起的 run——**按 meta 行 kind 选图**（ADR-007 唯一闸门）
- list()    run 列表（支持 kind/article_id 过滤）

线程模型：每 run 一个后台 daemon 线程；meta/checkpoint 双连接分离，
均 check_same_thread=False + timeout=30（跨线程安全靠 SQLite 串行写）。
浏览器层并发由 Hub 的 per-key 互斥 + browser_thread_run 专属线程兜底（本层不新增原语）。
"""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from workflows.graph import build_graph, build_update_graph

ROOT = Path(__file__).resolve().parent.parent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    id          TEXT PRIMARY KEY,
    article_id  INTEGER,
    title       TEXT,
    platforms   TEXT,
    status      TEXT,          -- running | waiting_human | done | failed
    result_json TEXT,         -- {'results': [...], 'decisions': [...], 'summary': {...}}
    error       TEXT,
    dry_run     INTEGER DEFAULT 0,
    kind        TEXT NOT NULL DEFAULT 'publish',   -- publish | update（M5/ADR-007）
    created_at  REAL,
    updated_at  REAL
);
CREATE INDEX IF NOT EXISTS idx_runs_updated ON workflow_runs(updated_at DESC);
"""

_KINDS = ('publish', 'update')


class WorkflowRunner:
    def __init__(self, hub, db_path=None):
        self.hub = hub
        self.db_path = Path(db_path or (ROOT / 'data' / 'workflow.db'))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # autocommit（isolation_level=None）：S5 扇出多 run 并行共享本连接，
        # 隐式事务会被跨线程 commit 撕出 "cannot commit - no transaction is active"；
        # 改自动提交后每条语句独立原子，跨线程按行键互不干扰（SQLite 层串行化）
        self._meta = sqlite3.connect(str(self.db_path), timeout=30,
                                     check_same_thread=False, isolation_level=None)
        self._meta.row_factory = sqlite3.Row
        self._meta.executescript(_SCHEMA)
        self._mig_error = self._migrate()
        self._ckpt_conn = sqlite3.connect(str(self.db_path), timeout=30,
                                          check_same_thread=False,
                                          isolation_level=None)
        self.saver = SqliteSaver(self._ckpt_conn)
        # 双图字典（ADR-007）：checkpointer 共用同一 SqliteSaver，按 meta 行 kind 路由
        self.graphs = {
            'publish': build_graph(hub, checkpointer=self.saver),
            'update': build_update_graph(hub, checkpointer=self.saver),
        }
        self._threads = {}
        self._lock = threading.Lock()

    def _migrate(self):
        """幂等迁移：存量库补 kind 列 + (kind, created_at) 索引（规格=docs/design/m5-data.md §1）。

        SQLite 的 ALTER TABLE ADD COLUMN 不支持 IF NOT EXISTS → 先 PRAGMA 探测。
        索引不能放 _SCHEMA：老库上建索引时列还不存在，会把整个 executescript 炸掉。
        返回 '' = 成功；非空 = 失败原因（拒绝服务 update 引擎，publish/legacy 不受影响，R6）。"""
        try:
            cols = [r[1] for r in self._meta.execute(
                "PRAGMA table_info(workflow_runs)").fetchall()]
            if cols and 'kind' not in cols:
                self._meta.execute(
                    "ALTER TABLE workflow_runs "
                    "ADD COLUMN kind TEXT NOT NULL DEFAULT 'publish'")
            self._meta.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_kind "
                "ON workflow_runs(kind, created_at DESC)")
            self._meta.commit()
            return ''
        except Exception as e:   # aqg: top-level boundary（迁移失败降级：拒绝 update 引擎）
            try:
                self._meta.rollback()
            except Exception:
                pass
            return f'{type(e).__name__}: {e}'

    # ---------------- 对外 API ----------------

    def start(self, article_id, platforms=None, account='default',
              draft_only=False, dry_run=False, kind='publish'):
        if kind not in _KINDS:
            raise ValueError(f'未知工作流类型: {kind}（可选 {_KINDS}）')
        if kind == 'update' and self._mig_error:
            raise RuntimeError(f'workflow.db 迁移失败，update 引擎不可用: {self._mig_error}')
        art = self.hub.get(article_id)
        if not art:
            raise ValueError(f'文章 {article_id} 不存在')

        target_pubs = {}
        if kind == 'update':
            # 目标实例同步预检（架构 §3.1：无 load_targets 节点，队列由 start 写入）。
            # B1：platforms 的 null/缺省/[] 三者等价 = 全部可更新实例（legacy 真值语义）。
            pubs = [dict(r) for r in self.hub.conn.execute(
                'SELECT * FROM publications WHERE article_id=?',
                (int(article_id),)).fetchall()]
            if platforms:
                pubs = [p for p in pubs if p['platform'] in platforms]
            pubs = [p for p in pubs if p['post_id'] or p['edit_url']]
            if not pubs:
                raise ValueError('没有已发布实例可更新，先 publish')
            target_pubs = {p['platform']: p for p in pubs}
            platforms = [p['platform'] for p in pubs]
        else:
            if not platforms:
                raise ValueError('platforms 为空，至少指定一个平台')

        run_id = uuid.uuid4().hex[:12]
        now = time.time()
        self._meta.execute(
            'INSERT INTO workflow_runs (id, article_id, title, platforms, status,'
            ' result_json, error, dry_run, kind, created_at, updated_at)'
            ' VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (run_id, int(article_id), art.get('title', ''),
             json.dumps(platforms, ensure_ascii=False), 'running',
             json.dumps({'results': [], 'decisions': []}, ensure_ascii=False),
             '', 1 if dry_run else 0, kind, now, now))
        self._meta.commit()

        if kind == 'update':
            state = {
                'run_id': run_id, 'article_id': int(article_id),
                'account': account, 'dry_run': bool(dry_run),
                'platforms_queue': list(platforms),
                'target_pubs': target_pubs,
                'results': [], 'decisions': [],
            }
        else:
            state = {
                'run_id': run_id, 'article_id': int(article_id),
                'platforms_queue': list(platforms), 'account': account,
                'draft_only': bool(draft_only), 'dry_run': bool(dry_run),
                'results': [], 'decisions': [],
            }
        self._spawn(run_id, state, kind=kind)
        return {'run_id': run_id, 'status': 'running',
                'poll': f'/runs/{run_id}'}

    def resume(self, run_id, approved=True, note=''):
        row = self._row(run_id)
        if not row:
            raise ValueError(f'run {run_id} 不存在')
        if row['status'] != 'waiting_human':
            raise ValueError(f'run {run_id} 状态为 {row["status"]}，仅 waiting_human 可恢复')
        t = self._threads.get(run_id)
        if t is not None and t.is_alive():
            raise ValueError('run 正在执行中，稍后再试')
        # kind 路由唯一闸门：resume 必须读 meta 行选图，禁止猜测（ADR-007）
        kind = row['kind'] if 'kind' in row.keys() else 'publish'
        self._meta.execute('UPDATE workflow_runs SET status=?, updated_at=? WHERE id=?',
                           ('running', time.time(), run_id))
        self._meta.commit()
        # resume 输入即 wait_human 节点 interrupt() 的返回值
        self._spawn(run_id, {'approved': bool(approved), 'note': note},
                    resume=True, kind=kind)
        return {'run_id': run_id, 'status': 'running'}

    def get(self, run_id):
        row = self._row(run_id)
        if not row:
            return None
        d = dict(row)
        kind = d.get('kind') or 'publish'
        d['kind'] = kind
        d['platforms'] = _safe_json(d.get('platforms'), [])
        try:
            d['result'] = _safe_json(d.pop('result_json'), {})
        except Exception:
            d['result'] = {}
        # checkpoint 实时进度（哪个节点、当前平台、剩余队列）
        try:
            snap = self.graphs[kind].get_state(
                {'configurable': {'thread_id': run_id}})
            vals = snap.values or {}
            d['checkpoint'] = {
                'node': (snap.next or [''])[0] if snap.next else '',
                'current_platform': vals.get('current_platform', ''),
                'attempts': vals.get('attempts', 0),
                'queue_left': len(vals.get('platforms_queue') or []),
            }
        except Exception:   # aqg: top-level boundary（checkpoint 读取失败不拦详情）
            d['checkpoint'] = {}
        return d

    def list(self, limit=50, kind=None, article_id=None):
        sql = ('SELECT id, article_id, title, platforms, status, error, dry_run,'
               ' kind, result_json, created_at, updated_at FROM workflow_runs')
        conds, args = [], []
        if kind:
            conds.append('kind=?')
            args.append(kind)
        if article_id is not None:
            conds.append('article_id=?')
            args.append(int(article_id))
        if conds:
            sql += ' WHERE ' + ' AND '.join(conds)
        sql += ' ORDER BY created_at DESC LIMIT ?'
        args.append(int(limit))
        rows = self._meta.execute(sql, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d['kind'] = d.get('kind') or 'publish'
            d['platforms'] = _safe_json(d.get('platforms'), [])
            res = _safe_json(d.pop('result_json'), {})
            # 列表只带前端等待卡片需要的字段，results/decisions 明细走 get()
            d['human_task'] = res.get('human_task')
            d['summary'] = res.get('summary')
            out.append(d)
        return out

    # ---------------- 内部 ----------------

    def _spawn(self, run_id, invoke_input, resume=False, kind='publish'):
        graph = self.graphs.get(kind or 'publish', self.graphs['publish'])

        def _run():
            cfg = {'configurable': {'thread_id': run_id}, 'recursion_limit': 100}
            try:
                res = graph.invoke(
                    Command(resume=invoke_input) if resume else invoke_input, cfg)
                payload = {
                    'results': res.get('results', []),
                    'decisions': res.get('decisions', []),
                    'summary': res.get('summary', {}),
                }
                status = 'done'
                if res.get('__interrupt__'):
                    status = 'waiting_human'
                    try:
                        payload['human_task'] = res['__interrupt__'][0].value
                    except Exception:
                        payload['human_task'] = {'message': '需要人工处理'}
                # 引擎级终止（文章缺失/门禁拒绝）记 failed，错误可见；
                # 平台级失败仍算 run 完成（done），细节看 summary
                fatal = (payload.get('summary') or {}).get('fatal')
                if fatal:
                    self._finish(run_id, 'failed', payload, str(fatal)[:300])
                else:
                    self._finish(run_id, status, payload, '')
            except Exception as e:   # aqg: top-level boundary（图执行异常落 failed 终态）
                self._finish(run_id, 'failed', None, f'{type(e).__name__}: {e}')
            finally:
                with self._lock:
                    self._threads.pop(run_id, None)

        t = threading.Thread(target=_run, daemon=True, name=f'wf-{run_id}')
        with self._lock:
            self._threads[run_id] = t
        t.start()

    def _finish(self, run_id, status, payload, error):
        # payload=None（异常路径）时保留既有 result_json，别把 human_task/历史冲掉
        if payload is None:
            self._meta.execute(
                'UPDATE workflow_runs SET status=?, error=?, updated_at=? WHERE id=?',
                (status, error, time.time(), run_id))
        else:
            self._meta.execute(
                'UPDATE workflow_runs SET status=?, result_json=?, error=?, updated_at=?'
                ' WHERE id=?',
                (status, json.dumps(payload, ensure_ascii=False),
                 error, time.time(), run_id))
        self._meta.commit()

    def _row(self, run_id):
        return self._meta.execute(
            'SELECT * FROM workflow_runs WHERE id=?', (run_id,)).fetchone()


def _safe_json(raw, default):
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return v if v is not None else default
    except Exception:
        return default
