# -*- coding: utf-8 -*-
"""人机协作冒烟：四种 wait_human 场景（不触真实平台）。

  A 重试回边      超时 → heuristic retry → 第二次成功 → done (attempts=2)
  B recover 场景  验证码 → 挂起(case=recover) → 恢复 → 回发布节点重试成功 → done
  C draft 确认    草稿回落 → 挂起(case=draft_confirm) → 恢复 → 发布实例翻转 ok → verify → done
  D draft 拒绝    草稿回落 → 挂起 → 拒绝 → run 收尾，发布实例保持 pending_human

用法: .venv/Scripts/python.exe scripts/smoke_hitl.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db
from core.adapters.base import PlatformError
from core.service import Hub
from workflows.runner import WorkflowRunner

ROOT = Path(__file__).resolve().parent.parent

# 过合规门禁长度线的正文（_local_review 要求 ≥200 字，且无占位符残留）
GATE_OK_CONTENT = ('这是一段用于通过合规门禁长度检查的测试正文，'
                   '讲述在工作流引擎里模拟平台失败行为的过程。' * 12)

ALL_OK = True


def check(label, ok, detail=''):
    global ALL_OK
    ALL_OK &= bool(ok)
    print(f'{"OK " if ok else "FAIL"} {label}' + (f' | {detail}' if detail else ''))


def wait_done(runner, run_id, timeout=90, expect=('done', 'failed')):
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = runner.get(run_id)
        if d['status'] in expect:
            return d
        time.sleep(1)
    return runner.get(run_id)


def cleanup(hub, aids):
    q = ','.join('?' * len(aids))
    hub.conn.execute(f'DELETE FROM articles WHERE id IN ({q})', aids)
    hub.conn.execute(f'DELETE FROM publications WHERE article_id IN ({q})', aids)
    hub.conn.commit()


def main():
    hub = Hub(headless=True)
    runner = WorkflowRunner(hub, db_path=ROOT / 'data' / 'workflow-smoke.db')
    aids = []

    # ---------- A：heuristic 重试回边 ----------
    aid = hub.create('冒烟A-重试回边', GATE_OK_CONTENT, source='human', status='draft')
    aids.append(aid)
    calls = {'n': 0}

    def flaky_then_ok(article_id, platform, article, **kw):
        calls['n'] += 1
        if calls['n'] == 1:
            raise PlatformError('请求超时 (timeout while waiting)')
        return {'platform': platform, 'ok': True, 'status': 'ok',
                'post_id': 'stub-a', 'post_url': '', 'edit_url': '', 'draft_only': ''}
    hub.publish_single = flaky_then_ok
    r = runner.start(aid, ['csdn'], draft_only=True)
    d = wait_done(runner, r['run_id'])
    res = d.get('result') or {}
    results, decisions = res.get('results', []), res.get('decisions', [])
    check('A 重试回边', d['status'] == 'done' and results and results[0].get('ok')
          and results[0].get('attempts') == 2
          and decisions and decisions[0]['action'] == 'retry'
          and decisions[0]['by'] == 'heuristic',
          f'终态={d["status"]} attempts={results[0].get("attempts") if results else "-"}')

    # ---------- B：recover 场景（验证码 → 挂起 → 恢复 → 重试成功） ----------
    aid = hub.create('冒烟B-故障恢复', GATE_OK_CONTENT, source='human', status='draft')
    aids.append(aid)
    bcalls = {'n': 0}

    def captcha_then_ok(article_id, platform, article, **kw):
        bcalls['n'] += 1
        if bcalls['n'] == 1:
            raise PlatformError('发布被风控拦截：出现验证码 (captcha)')
        return {'platform': platform, 'ok': True, 'status': 'ok',
                'post_id': 'stub-b', 'post_url': '', 'edit_url': '', 'draft_only': ''}
    hub.publish_single = captcha_then_ok
    r = runner.start(aid, ['csdn'], draft_only=True)
    d1 = wait_done(runner, r['run_id'], expect=('waiting_human', 'done', 'failed'))
    task = (d1.get('result') or {}).get('human_task') or {}
    check('B1 挂起(case=recover)', d1['status'] == 'waiting_human'
          and task.get('case') == 'recover'
          and '验证码' in (task.get('error') or ''),
          f'case={task.get("case")} msg={str(task.get("message"))[:50]}')
    runner.resume(r['run_id'], approved=True, note='人工已过验证码')
    d2 = wait_done(runner, r['run_id'])
    res2 = d2.get('result') or {}
    r2list = res2.get('results', [])
    check('B2 恢复后回发布重试成功', d2['status'] == 'done' and r2list
          and r2list[0].get('ok') and bcalls['n'] == 2,
          f'终态={d2["status"]} 平台调用={bcalls["n"]}次')

    # ---------- C：draft_confirm 确认（翻转 pending_human→ok → verify → done） ----------
    aid = hub.create('冒烟C-草稿确认', GATE_OK_CONTENT, source='human', status='draft')
    aids.append(aid)
    db.upsert_publication(hub.conn, aid, 'juejin', 'default',
                          post_id='draft-smoke-c',
                          edit_url='https://juejin.cn/editor/drafts/draft-smoke-c',
                          status='pending_human', draft_only=1)

    def draft_fallback(article_id, platform, article, **kw):
        return {'platform': platform, 'ok': True, 'status': 'pending_human',
                'post_id': 'draft-smoke-c', 'post_url': '',
                'edit_url': 'https://juejin.cn/editor/drafts/draft-smoke-c',
                'draft_only': True}
    hub.publish_single = draft_fallback
    r = runner.start(aid, ['juejin'], draft_only=False)
    d1 = wait_done(runner, r['run_id'], expect=('waiting_human', 'done', 'failed'))
    task = (d1.get('result') or {}).get('human_task') or {}
    check('C1 挂起(case=draft_confirm)', d1['status'] == 'waiting_human'
          and task.get('case') == 'draft_confirm'
          and 'editor/drafts' in (task.get('edit_url') or ''),
          f'edit_url={task.get("edit_url")}')
    runner.resume(r['run_id'], approved=True, note='冒烟C人工确认')
    d2 = wait_done(runner, r['run_id'])
    res2 = d2.get('result') or {}
    r2list = res2.get('results', [])
    pub = hub.conn.execute(
        'SELECT status, draft_only FROM publications WHERE article_id=? AND platform=?',
        (aid, 'juejin')).fetchone()
    check('C2 恢复→翻转→verify→done', d2['status'] == 'done' and r2list
          and r2list[0].get('status') == 'ok'
          and r2list[0].get('note') == '冒烟C人工确认'
          and pub and pub['status'] == 'ok' and pub['draft_only'] == 0,
          f'终态={d2["status"]} pub={dict(pub) if pub else None} '
          f'verify={r2list[0].get("verify") if r2list else "-"}')

    # ---------- D：draft_confirm 拒绝（发布实例保持 pending_human） ----------
    aid = hub.create('冒烟D-草稿拒绝', GATE_OK_CONTENT, source='human', status='draft')
    aids.append(aid)
    db.upsert_publication(hub.conn, aid, 'juejin', 'default',
                          post_id='draft-smoke-d',
                          edit_url='https://juejin.cn/editor/drafts/draft-smoke-d',
                          status='pending_human', draft_only=1)
    r = runner.start(aid, ['juejin'], draft_only=False)
    d1 = wait_done(runner, r['run_id'], expect=('waiting_human', 'done', 'failed'))
    check('D1 挂起', d1['status'] == 'waiting_human')
    runner.resume(r['run_id'], approved=False, note='先不发')
    d2 = wait_done(runner, r['run_id'])
    res2 = d2.get('result') or {}
    r2list = res2.get('results', [])
    pub = hub.conn.execute(
        'SELECT status FROM publications WHERE article_id=? AND platform=?',
        (aid, 'juejin')).fetchone()
    check('D2 拒绝→run 收尾+发布实例保持待人工', d2['status'] == 'done' and r2list
          and r2list[0].get('status') == 'pending_human'
          and '先不发' in (r2list[0].get('note') or '')
          and pub and pub['status'] == 'pending_human',
          f'终态={d2["status"]} pub={dict(pub) if pub else None}')

    cleanup(hub, aids)
    print(f'\n总断言: {"PASS" if ALL_OK else "FAIL"}')
    sys.exit(0 if ALL_OK else 1)


if __name__ == '__main__':
    main()
