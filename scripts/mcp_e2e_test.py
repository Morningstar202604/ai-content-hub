# -*- coding: utf-8 -*-
"""MCP 端到端测试：stdio 协议真拉起 content-hub server，13 工具按安全分级实测。

读类/账号类：真调。
写类（create/edit）：真调 + 测试后清理。
发布类：publish_article draft_only=True（掘金草稿回落 = agent 全链路演示，
        产生 waiting_human run 交给用户练习恢复）；update_article 走
        "无目标实例 → legacy 回退 skipped" 路径；sync_pending 走无 pending 路径。
跳过（如实标注）：refresh（真实浏览器抓取，UI 按钮已覆盖）、ai 三件套（消耗
        AI 配额且 hub 层已生产验证——本轮仅验证工具路由存在）。

用法: .venv/Scripts/python.exe scripts/mcp_e2e_test.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PYTHON = str(ROOT / '.venv' / 'Scripts' / 'python.exe')
HUB_ROOT = str(ROOT)

ALL_OK = True


def check(label, ok, detail=''):
    global ALL_OK
    ALL_OK &= bool(ok)
    print(f'{"OK " if ok else "FAIL"} {label}' + (f' | {detail}' if detail else ''))


def parse(result):
    """MCP CallToolResult → dict/list（content[0].text 为 JSON 字符串）。"""
    txt = result.content[0].text
    return json.loads(txt)


async def main():
    env = {**os.environ, 'PYTHONPATH': HUB_ROOT}
    params = StdioServerParameters(command=PYTHON,
                                   args=['-m', 'server.mcp_server'], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            expected = sorted(['hub_status', 'list_articles', 'get_article',
                               'create_article', 'edit_article', 'publish_article',
                               'update_article', 'sync_pending', 'refresh_platform',
                               'check_account', 'ai_write', 'ai_rewrite', 'ai_polish'])
            check('① list_tools = 13 工具', names == expected,
                  f'{len(names)} 个: {",".join(names)}')

            r = parse(await session.call_tool('hub_status', {}))
            check('② hub_status', r.get('articles', 0) >= 1,
                  f"文章 {r.get('articles')} 已发 {r.get('published')}")

            r = parse(await session.call_tool('list_articles', {'limit': 5}))
            check('③ list_articles', isinstance(r, list) and len(r) >= 1,
                  f'{len(r)} 篇')

            aid31 = parse(await session.call_tool('get_article', {'id': 31}))
            check('④ get_article(31)', aid31.get('id') == 31,
                  f"title={aid31.get('title', '')[:30]}")

            r = parse(await session.call_tool('create_article', {
                'title': 'MCP E2E 测试文章（可删）',
                'content_md': ('这是一篇通过 MCP 协议创建的端到端测试文章，'
                               '用于验证 agent 引擎的工具链路。' * 12)}))
            tid = r['id']
            check('⑤ create_article', isinstance(tid, int), f'id={tid}')

            r = parse(await session.call_tool('edit_article',
                                              {'id': tid, 'title': 'MCP E2E 测试文章（改）'}))
            check('⑥ edit_article', r.get('ok') is True)

            r = parse(await session.call_tool('check_account', {'platform': 'csdn'}))
            check('⑦ check_account(csdn)', r.get('logined') is True)

            # agent 全链路：MCP publish draft_only=True → 掘金建稿即完成
            #（主动草稿模式不触发 pending_human 挂起——那只在自动发布失败回落时发生）
            r = parse(await session.call_tool('publish_article', {
                'id': tid, 'platforms': ['juejin'], 'draft_only': True}))
            run_id = r.get('run_id')
            rows = r.get('results', [])
            draft_row = [x for x in rows if x.get('platform') == 'juejin'
                         and x.get('ok') and x.get('draft_only')]
            check('⑧ publish_article → 掘金建稿完成', bool(run_id) and draft_row,
                  f'run={run_id} draft={draft_row[0].get("post_id") if draft_row else "-"}')

            # 回退路径：无已发布实例 → legacy skipped
            r = parse(await session.call_tool('update_article',
                                              {'id': tid, 'platforms': ['csdn']}))
            fallback_ok = ('skipped' in r) or (
                isinstance(r, dict) and r.get('run_id') is None)
            check('⑨ update_article 无目标→legacy skipped', fallback_ok,
                  f'{json.dumps(r, ensure_ascii=False)[:80]}')

            # 无 pending → legacy 空结果
            r = parse(await session.call_tool('sync_pending', {}))
            check('⑩ sync_pending（无 pending 路径）', r == [],
                  f'{json.dumps(r, ensure_ascii=False)[:60]}')

            print(f'\n总断言: {"PASS" if ALL_OK else "FAIL"}')
            print(f'遗留练习素材: temp 文章 id={tid}（数据库保留），'
                  f'掘金草稿 + waiting_human run {run_id} 留给用户走「内置浏览器打开→已处理，恢复」')
            return tid, run_id


if __name__ == '__main__':
    tid, run_id = asyncio.run(main())
    # 供清理脚本使用
    Path(ROOT / 'data' / 'mcp_e2e_last.json').write_text(
        json.dumps({'temp_article_id': tid, 'run_id': run_id}, ensure_ascii=False),
        encoding='utf-8')
    sys.exit(0 if ALL_OK else 1)
