# -*- coding: utf-8 -*-
"""MCP E2E 第二轮：上一轮跳过的高成本工具真测（refresh / ai_write / ai_polish）。

全部经 stdio 协议真拉起 server 调用；AI 走用户配置的真模型（agnes-3.0-flash）；
refresh 走真实浏览器抓取。测试产物（AI 文章）测后清理。

用法: .venv/Scripts/python.exe scripts/mcp_e2e_round2.py
"""
import asyncio
import json
import os
import sqlite3
import sys
from datetime import timedelta
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


async def call(session, name, args, timeout_s=300):
    """带超时的工具调用（兼容有无 read_timeout_seconds 参数的 SDK 版本）。"""
    try:
        r = await asyncio.wait_for(
            session.call_tool(name, args, read_timeout_seconds=timedelta(seconds=timeout_s)),
            timeout=timeout_s + 30)
    except TypeError:
        r = await asyncio.wait_for(session.call_tool(name, args),
                                   timeout=timeout_s + 30)
    return json.loads(r.content[0].text)


async def main():
    env = {**os.environ, 'PYTHONPATH': HUB_ROOT}
    params = StdioServerParameters(command=PYTHON,
                                   args=['-m', 'server.mcp_server'], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ---------- ① refresh_platform：真实浏览器抓取 CSDN 文章列表 ----------
            r = await call(session, 'refresh_platform', {'platform': 'csdn'}, 240)
            check('① refresh_platform(csdn) 真实抓取',
                  isinstance(r, dict) and 'count' in r,
                  f"抓回 {r.get('count')} 篇 / 存 {r.get('saved')}")

            # ---------- ② ai_write：真 AI 写稿 + AIGC 标识 + 门禁 ----------
            r = await call(session, 'ai_write', {
                'topic': '为什么我们的发布引擎要用单线程跑浏览器',
                'words': 500}, 300)
            aid = r.get('id')
            labeled = r.get('aigc_labeled')
            chars = r.get('chars', 0)
            check('② ai_write 真写稿', isinstance(aid, int) and labeled is True
                  and chars > 200, f'id={aid} aigc={labeled} chars={chars}')

            # ---------- ③ ai_polish：真 AI 润色 ----------
            r = await call(session, 'ai_polish', {'id': aid}, 300)
            check('③ ai_polish', r.get('id') == aid,
                  f"id={r.get('id')} pending_sync={r.get('pending_sync')}")

            # ---------- 数据库侧核实：AIGC 标识 + jobs 留痕 ----------
            conn = sqlite3.connect(str(ROOT / 'data' / 'hub.db'))
            conn.row_factory = sqlite3.Row
            art = conn.execute('SELECT title, source, ai_model, ext FROM articles '
                               'WHERE id=?', (aid,)).fetchone()
            ext = json.loads(art['ext'] or '{}') if art else {}
            check('④ AIGC 标识入库', art is not None and ext.get('aigc') is True
                  and art['source'] == 'ai' and art['ai_model'],
                  f"model={art['ai_model'] if art else '-'} aigc={ext.get('aigc')}")

            # ---------- 清理 AI 测试文章 ----------
            conn.execute('DELETE FROM articles WHERE id=?', (aid,))
            conn.execute('DELETE FROM publications WHERE article_id=?', (aid,))
            conn.execute('DELETE FROM jobs WHERE article_id=?', (aid,))
            conn.commit()
            conn.close()
            print('清理: AI 测试文章已删（真实 AI 调用消耗已发生）')

    print(f'\n总断言: {"PASS" if ALL_OK else "FAIL"}')
    sys.exit(0 if ALL_OK else 1)


if __name__ == '__main__':
    asyncio.run(main())
