# -*- coding: utf-8 -*-
"""M5 冒烟：update 工作流 S1–S5 + S6 双跑对账（R3 门禁，不触真实平台）。

浏览器层用桩（hub._with_adapter / hub.update_single），闸门与记账走真实代码：
  S1 dry_run 双平台   图跑通/results 全 ok/meta kind=update/summary 无 pending_human
  S2 重试回边         注入超时失败桩 → heuristic retry → 第二次成功（attempts=2）
  S3 门禁 fatal       不合规内容 dry_run=False → run failed/浏览器零调用/错误含"门禁"
  S4 recover 挂起恢复 验证码桩 → waiting_human(case=recover) → resume → 回 update_instance → done
  S5 sync 扇出        2 篇 pending → 端点 count=2/两 run done/pending 清零/publications ok
  S6 双跑对账(R3)     同场景 legacy hub.update() vs 引擎 run：publications/jobs 终态 diff 断言

用法: .venv/Scripts/python.exe scripts/smoke_update.py
"""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db
from core.adapters.base import PlatformError
from core.service import Hub
from workflows.runner import WorkflowRunner

ROOT = Path(__file__).resolve().parent.parent

# 过合规门禁长度线的正文（_local_review 要求 ≥200 字，且无占位符残留）
GATE_OK_CONTENT = ('这是一段用于通过合规门禁长度检查的测试正文，'
                   '讲述在工作流引擎里验证原地更新链路的过程。' * 12)

ALL_OK = True


def check(label, ok, detail=''):
    global ALL_OK
    ALL_OK &= bool(ok)
    print(f'{"OK " if ok else "FAIL"} {label}' + (f' | {detail}' if detail else ''))


def wait_status(runner, run_id, statuses=('done', 'failed'), timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = runner.get(run_id)
        if d['status'] in statuses:
            return d
        time.sleep(1)
    return runner.get(run_id)


def fake_browser_layer(hub):
    """浏览器层桩：_with_adapter 不开浏览器，直接让 fn 在内存里成功。"""
    def _stub(pf, account, fn, page_hook=None):
        return fn(SimpleNamespace(update=lambda page, pub, article: True), None)
    hub._with_adapter = _stub
    hub.delay_article = (0, 0)   # 冒烟不留风控间隔


def make_article(hub, title, platforms, pub_status='ok', content=None):
    aid = hub.create(title, content or GATE_OK_CONTENT,
                     source='human', status='draft')
    for pf in platforms:
        db.upsert_publication(hub.conn, aid, pf, 'default',
                              post_id=f'post-{pf}-{aid}',
                              post_url=f'https://example.com/{pf}/{aid}',
                              edit_url=f'https://example.com/edit/{pf}/{aid}',
                              status=pub_status, draft_only=0)
    return aid


def cleanup(hub, aids):
    q = ','.join('?' * len(aids))
    hub.conn.execute(f'DELETE FROM articles WHERE id IN ({q})', aids)
    hub.conn.execute(f'DELETE FROM publications WHERE article_id IN ({q})', aids)
    hub.conn.execute(f'DELETE FROM jobs WHERE article_id IN ({q})', aids)
    hub.conn.commit()


def pub_status_map(hub, aid):
    return {r['platform']: r['status'] for r in hub.conn.execute(
        'SELECT platform, status FROM publications WHERE article_id=?', (aid,))}


def main():
    hub = Hub(headless=True)
    runner = WorkflowRunner(hub, db_path=ROOT / 'data' / 'workflow-smoke.db')
    fake_browser_layer(hub)
    aids = []

    # ---------- S1：dry_run 双平台 ----------
    aid = make_article(hub, '冒烟S1-update-dry双平台', ['csdn', 'zhihu'])
    aids.append(aid)
    r = runner.start(aid, ['csdn', 'zhihu'], kind='update', dry_run=True)
    d = wait_status(runner, r['run_id'], ('done', 'failed', 'waiting_human'))
    res = d.get('result') or {}
    in_update_list = any(x['id'] == d['id'] for x in runner.list(kind='update'))
    not_in_publish = all(x['id'] != d['id'] for x in runner.list(kind='publish'))
    check('S1 dry_run 双平台', d['status'] == 'done'
          and len(res.get('results', [])) == 2
          and all(x.get('ok') for x in res['results'])
          and d.get('kind') == 'update'
          and (res.get('summary') or {}).get('targets_ok') == 2
          and 'pending_human' not in (res.get('summary') or {})
          and in_update_list and not_in_publish,
          f'终态={d["status"]} kind={d.get("kind")} '
          f'targets_ok={(res.get("summary") or {}).get("targets_ok")}')

    # ---------- S2：重试回边 ----------
    ORIG_UPDATE_SINGLE = hub.update_single   # 桩恢复锚点（S4 的桩若不还原会污染 S6）
    aid = make_article(hub, '冒烟S2-update重试回边', ['csdn'])
    aids.append(aid)
    calls = {'n': 0}

    def flaky(article_id, platform, pub, article, **kw):
        calls['n'] += 1
        if calls['n'] == 1:
            raise PlatformError('请求超时 (timeout while waiting)')
        return {'platform': platform, 'ok': True}
    hub.update_single = flaky
    r = runner.start(aid, ['csdn'], kind='update')
    d = wait_status(runner, r['run_id'])
    res = d.get('result') or {}
    decisions = res.get('decisions', [])
    check('S2 重试回边', d['status'] == 'done'
          and res.get('results') and res['results'][0].get('ok')
          and res['results'][0].get('attempts') == 2
          and decisions and decisions[0]['action'] == 'retry'
          and decisions[0]['by'] == 'heuristic',
          f'终态={d["status"]} attempts={res["results"][0].get("attempts") if res.get("results") else "-"}')

    # ---------- S3：门禁 fatal（不开浏览器） ----------
    aid = make_article(hub, '冒烟S3-门禁拒绝', ['csdn'], content='太短')
    aids.append(aid)
    probe = {'n': 0}

    def _must_not_run(*a, **kw):
        probe['n'] += 1
        return {'platform': 'csdn', 'ok': True}
    hub.update_single = _must_not_run
    r = runner.start(aid, ['csdn'], kind='update')   # dry_run=False → 门禁真跑
    d = wait_status(runner, r['run_id'])
    check('S3 门禁 fatal', d['status'] == 'failed'
          and '门禁' in (d.get('error') or '')
          and probe['n'] == 0,
          f'终态={d["status"]} error={(d.get("error") or "")[:60]} 浏览器调用={probe["n"]}')

    # ---------- S4：recover 挂起 → 恢复 ----------
    aid = make_article(hub, '冒烟S4-update-recover', ['csdn'])
    aids.append(aid)
    bcalls = {'n': 0}

    def captcha_then_ok(article_id, platform, pub, article, **kw):
        bcalls['n'] += 1
        if bcalls['n'] == 1:
            raise PlatformError('更新被风控拦截：出现验证码 (captcha)')
        return {'platform': platform, 'ok': True}
    hub.update_single = captcha_then_ok
    r = runner.start(aid, ['csdn'], kind='update')
    d1 = wait_status(runner, r['run_id'], ('waiting_human', 'done', 'failed'))
    task = (d1.get('result') or {}).get('human_task') or {}
    check('S4a 挂起(case=recover)', d1['status'] == 'waiting_human'
          and task.get('case') == 'recover',
          f'case={task.get("case")} msg={str(task.get("message"))[:50]}')
    runner.resume(r['run_id'], approved=True, note='人工已过验证码')
    d2 = wait_status(runner, r['run_id'])
    res2 = d2.get('result') or {}
    check('S4b 恢复→回 update_instance→done', d2['status'] == 'done'
          and res2.get('results') and res2['results'][0].get('ok')
          and bcalls['n'] == 2,
          f'终态={d2["status"]} 平台调用={bcalls["n"]}次')

    # ---------- S5：sync 扇出（走真实端点函数） ----------
    fake_browser_layer(hub)   # S2–S4 换过桩，恢复浏览器层桩
    aid1 = make_article(hub, '冒烟S5-扇出A', ['csdn', 'zhihu'], pub_status='pending')
    aid2 = make_article(hub, '冒烟S5-扇出B', ['csdn'], pub_status='pending')
    aids += [aid1, aid2]
    import server.api as sapi
    sapi.hub._with_adapter = hub._with_adapter        # 服务端实例同款浏览器层桩
    sapi.hub.delay_article = (0, 0)
    sapi._RUNNER = WorkflowRunner(sapi.hub,
                                  db_path=ROOT / 'data' / 'workflow-smoke.db')
    r = sapi.sync_pending_workflow(sapi.WorkflowSyncIn(dry_run=False))
    ok_fanout = (r.get('count') == 2 and len(r.get('runs', [])) == 2
                 and r.get('failed') == [])
    for s in r.get('runs', []):
        wait_status(sapi._RUNNER, s['run_id'], ('done', 'failed', 'waiting_human'))
    statuses = [sapi._RUNNER.get(s['run_id'])['status'] for s in r.get('runs', [])]
    pending_after = [row for row in db.get_pending_updates(hub.conn)
                     if row['article_id'] in (aid1, aid2)]
    s5_maps = {aid: pub_status_map(hub, aid) for aid in (aid1, aid2)}
    check('S5 sync 扇出', ok_fanout and all(s == 'done' for s in statuses)
          and len(pending_after) == 0
          and all(v == 'ok' for m in s5_maps.values() for v in m.values()),
          f'count={r.get("count")} failed={r.get("failed")} '
          f'statuses={statuses} pending残留={len(pending_after)}')

    # ---------- S6：legacy/引擎双跑 DB 对账（R3 门禁） ----------
    fake_browser_layer(hub)
    hub.update_single = ORIG_UPDATE_SINGLE   # 还原真身：S6 要走真实 update_single 记账
    aidA = make_article(hub, '冒烟S6A-legacy双跑', ['csdn', 'zhihu'],
                        pub_status='pending')
    aidB = make_article(hub, '冒烟S6B-engine双跑', ['csdn', 'zhihu'],
                        pub_status='pending')
    aids += [aidA, aidB]
    hub.update(aidA)                                        # legacy 路径
    rb = runner.start(aidB, ['csdn', 'zhihu'], kind='update')  # 引擎路径
    wait_status(runner, rb['run_id'])
    mapA, mapB = pub_status_map(hub, aidA), pub_status_map(hub, aidB)
    jobsA = hub.conn.execute(
        'SELECT platform, status FROM jobs WHERE article_id=? AND type="update"',
        (aidA,)).fetchall()
    jobsB = hub.conn.execute(
        'SELECT platform, status FROM jobs WHERE article_id=? AND type="update"',
        (aidB,)).fetchall()
    check('S6 双跑 DB 对账(R3 门禁)',
          mapA == mapB and all(v == 'ok' for v in mapA.values())
          and len(jobsA) == len(jobsB) == 2,
          f'legacy={mapA} engine={mapB} jobs={len(jobsA)}/{len(jobsB)}')

    cleanup(hub, aids)
    print(f'\n总断言: {"PASS" if ALL_OK else "FAIL"}')
    sys.exit(0 if ALL_OK else 1)


if __name__ == '__main__':
    main()
