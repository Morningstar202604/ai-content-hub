# -*- coding: utf-8 -*-
"""RunManager：发布工作流的执行器（运行模型见 ARCHITECTURE.md §3.4）。

Run 状态机：running → waiting_human → running → done | failed
- start()   建 run 记录 + 后台线程跑图（checkpoint 持久化到 data/workflow.db）
- get()     run 详情（结果 + 人工任务载荷 + checkpoint 实时进度）
- resume()  人在前端完成平台侧操作后恢复挂起的 run
- list()    run 列表

线程模型：每 run 一个后台线程；meta 连接与 checkpoint 连接分离，
均 check_same_thread=False + timeout=30（跨线程安全靠 SQLite 串行写）。
"""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from workflows.graph import build_graph

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
    created_at  REAL,
    updated_at  REAL
);
CREATE INDEX IF NOT EXISTS idx_runs_updated ON workflow_runs(updated_at DESC);
"""


class WorkflowRunner:
    def __init__(self, hub, db_path=None):
        self.hub = hub
        self.db_path = Path(db_path or (ROOT / 'data' / 'workflow.db'))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._meta = sqlite3.connect(str(self.db_path), timeout=30,
                                     check_same_thread=False)
        self._meta.row_factory = sqlite3.Row
        self._meta.executescript(_SCHEMA)
        self._meta.commit()
        self._ckpt_conn = sqlite3.connect(str(self.db_path), timeout=30,
                                          check_same_thread=False)
        self.saver = SqliteSaver(self._ckpt_conn)
        self.graph = build_graph(hub, checkpointer=self.saver)
        self._threads = {}
        self._lock = threading.Lock()

    # ---------------- 对外 API ----------------

    def start(self, article_id, platforms, account='default',
              draft_only=False, dry_run=False):
        art = self.hub.get(article_id)
        if not art:
            raise ValueError(f'文章 {article_id} 不存在')
        if not platforms:
            raise ValueError('platforms 为空，至少指定一个平台')
        run_id = uuid.uuid4().hex[:12]
        now = time.time()
        self._meta.execute(
            'INSERT INTO workflow_runs (id, article_id, title, platforms, status,'
            ' result_json, error, dry_run, created_at, updated_at)'
            ' VALUES (?,?,?,?,?,?,?,?,?,?)',
            (run_id, int(article_id), art.get('title', ''),
             json.dumps(platforms, ensure_ascii=False), 'running',
             json.dumps({'results': [], 'decisions': []}, ensure_ascii=False),
             '', 1 if dry_run else 0, now, now))
        self._meta.commit()
        state = {
            'run_id': run_id, 'article_id': int(article_id),
            'platforms_queue': list(platforms), 'account': account,
            'draft_only': bool(draft_only), 'dry_run': bool(dry_run),
            'results': [], 'decisions': [],
        }
        self._spawn(run_id, state)
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
        self._meta.execute('UPDATE workflow_runs SET status=?, updated_at=? WHERE id=?',
                           ('running', time.time(), run_id))
        self._meta.commit()
        # resume 输入即 wait_human 节点 interrupt() 的返回值
        self._spawn(run_id, {'approved': bool(approved), 'note': note}, resume=True)
        return {'run_id': run_id, 'status': 'running'}

    def get(self, run_id):
        row = self._row(run_id)
        if not row:
            return None
        d = dict(row)
        d['platforms'] = _safe_json(d.get('platforms'), [])
        try:
            d['result'] = _safe_json(d.pop('result_json'), {})
        except Exception:
            d['result'] = {}
        # checkpoint 实时进度（哪个节点、当前平台、剩余队列）
        try:
            snap = self.graph.get_state({'configurable': {'thread_id': run_id}})
            vals = snap.values or {}
            d['checkpoint'] = {
                'node': (snap.next or [''])[0] if snap.next else '',
                'current_platform': vals.get('current_platform', ''),
                'attempts': vals.get('attempts', 0),
                'queue_left': len(vals.get('platforms_queue') or []),
            }
        except Exception:
            d['checkpoint'] = {}
        return d

    def list(self, limit=50):
        rows = self._meta.execute(
            'SELECT id, article_id, title, platforms, status, error, dry_run,'
            ' result_json, created_at, updated_at FROM workflow_runs'
            ' ORDER BY created_at DESC LIMIT ?', (int(limit),)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d['platforms'] = _safe_json(d.get('platforms'), [])
            res = _safe_json(d.pop('result_json'), {})
            # 列表只带前端等待卡片需要的字段，results/decisions 明细走 get()
            d['human_task'] = res.get('human_task')
            d['summary'] = res.get('summary')
            out.append(d)
        return out

    # ---------------- 内部 ----------------

    def _spawn(self, run_id, invoke_input, resume=False):
        def _run():
            cfg = {'configurable': {'thread_id': run_id}, 'recursion_limit': 100}
            try:
                res = self.graph.invoke(
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
            except Exception as e:
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
