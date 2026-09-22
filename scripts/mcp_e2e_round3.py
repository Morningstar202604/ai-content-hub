# -*- coding: utf-8 -*-
"""MCP E2E 第三轮：ai_rewrite（最后一个未直调的工具）。真 AI 调用，测后清理。"""
import asyncio
import json
import os
import sqlite3
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
    return json.loads(result.content[0].text)


async def main():
    env = {**os.environ, 'PYTHONPATH': HUB_ROOT}
    params = StdioServerParameters(command=PYTHON,
                                   args=['-m', 'server.mcp_server'], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            r = json.loads((await session.call_tool('create_article', {
                'title': 'MCP E2E r3 改写测试（可删）',
                'content_md': ('这是一篇用于验证 ai_rewrite 工具的测试文章，'
                               '内容讲述一个发布引擎把多平台文章原地更新的流程。' * 10)})).content[0].text)
            aid = r['id']

            r = json.loads((await asyncio.wait_for(
                session.call_tool('ai_rewrite',
                                  {'id': aid,
                                   'instruction': '把标题保留，正文最后加一句：本文由引擎改写流程验证。'},
                                  read_timeout_seconds=300.0),
                timeout=330)).content[0].text)
            check('ai_rewrite 真改写', r.get('id') == aid and r.get('chars', 0) > 200,
                  f"id={r.get('id')} chars={r.get('chars')}")

            conn = sqlite3.connect(str(ROOT / 'data' / 'hub.db'))
            body = conn.execute('SELECT content_md FROM articles WHERE id=?',
                                (aid,)).fetchone()[0]
            check('改写内容落库', '引擎改写流程验证' in body)
            conn.execute('DELETE FROM articles WHERE id=?', (aid,))
            conn.execute('DELETE FROM jobs WHERE article_id=?', (aid,))
            conn.commit()
            conn.close()
            print('清理: 改写测试文章已删')

    print(f'\n总断言: {"PASS" if ALL_OK else "FAIL"}')
    sys.exit(0 if ALL_OK else 1)


if __name__ == '__main__':
    asyncio.run(main())
