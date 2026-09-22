# -*- coding: utf-8 -*-
"""M1 冒烟：dry_run 工作流发布（不触真实平台，ADR-005）。

验证路径：建文 → WorkflowRunner.start(dry_run) → 图执行
（load→gate→[login→publish→verify→triage]×2→aggregate）→ 落库可查 → 清理。

用法: .venv/Scripts/python.exe scripts/smoke_workflow.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.service import Hub
from workflows.runner import WorkflowRunner


def main():
    hub = Hub(headless=True)
    aid = hub.create('工作流冒烟测试（可删除）', '# 冒烟\n\ndry_run 测试正文。',
                     source='human', status='draft')
    print(f'[1] 测试文章 aid={aid}')

    # 用独立 smoke db，不污染正式 workflow.db
    root = Path(__file__).resolve().parent.parent
    runner = WorkflowRunner(hub, db_path=root / 'data' / 'workflow-smoke.db')
    r = runner.start(aid, ['csdn', 'zhihu'], draft_only=True, dry_run=True)
    run_id = r['run_id']
    print(f'[2] run_id={run_id} 已启动，轮询中…')

    deadline = time.time() + 60
    while time.time() < deadline:
        d = runner.get(run_id)
        if d['status'] in ('done', 'failed'):
            break
        time.sleep(1)

    d = runner.get(run_id)
    print(f'[3] 终态: {d["status"]} | checkpoint={d.get("checkpoint")}')
    res = d.get('result') or {}
    for it in res.get('results', []):
        print(f'    - {it.get("platform")}: ok={it.get("ok")} status={it.get("status")}'
              f' post_id={it.get("post_id")} verify={it.get("verify")}')
    print(f'[4] summary={json.dumps(res.get("summary", {}), ensure_ascii=False)}')

    # 断言：终态 done、两平台结果齐全且 ok、summary.ok
    results = res.get('results', [])
    ok = (d['status'] == 'done'
          and len(results) == 2
          and all(x.get('ok') for x in results)
          and (res.get('summary') or {}).get('ok') is True)

    # 负面断言：非 waiting_human 的 run 不允许 resume
    try:
        runner.resume(run_id, approved=True)
        ok = False
        print('[5] ✗ 负面断言失败：非挂起 run 竟可 resume')
    except ValueError as e:
        print(f'[5] ✓ 负面断言通过：resume 被正确拒绝（{e}）')

    # 清理：测试文章从 hub.db 删除（smoke run 记录留在 workflow-smoke.db 不碍事）
    hub.conn.execute('DELETE FROM articles WHERE id=?', (aid,))
    hub.conn.commit()
    print(f'[6] 测试文章已清理 | 断言: {"✅ PASS" if ok else "❌ FAIL"}')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
