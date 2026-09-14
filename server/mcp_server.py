# -*- coding: utf-8 -*-
"""MCP Server：让 AI 客户端（Claude Code 等）直接接管整个中台。

手写的极简 MCP（stdio + 换行分隔 JSON），不引第三方依赖，加起来一百多行。
配置到客户端：
    {
      "mcpServers": {
        "content-hub": {
          "command": "python",
          "args": ["-m", "server.mcp_server"]
        }
      }
    }
之后 AI 就能说："写篇讲 XXX 的文章发到掘金" / "把 3 号文章改个标题同步到全部平台"。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.service import Hub

hub = Hub(headless=True)

TOOLS = [
    {"name": "hub_status", "description": "中台总览：文章数、发布数、待同步数、账号状态",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_articles", "description": "列出文章（可按状态过滤）",
     "inputSchema": {"type": "object", "properties": {"status": {"type": "string"}, "limit": {"type": "integer"}}}},
    {"name": "get_article", "description": "按 ID 读文章全文",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}},
    {"name": "create_article", "description": "新建文章（AI 写稿入库）",
     "inputSchema": {"type": "object", "properties": {
         "title": {"type": "string"}, "content_md": {"type": "string"},
         "summary": {"type": "string"}, "tags": {"type": "string"},
         "ai_model": {"type": "string"}}, "required": ["title"]}},
    {"name": "edit_article", "description": "改文章。改完自动把已发布实例标为待同步",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "integer"}, "title": {"type": "string"},
         "content_md": {"type": "string"}, "summary": {"type": "string"},
         "tags": {"type": "string"}}, "required": ["id"]}},
    {"name": "publish_article", "description": "发布到指定平台",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "integer"}, "platforms": {"type": "array", "items": {"type": "string"}},
         "draft_only": {"type": "boolean"}}, "required": ["id", "platforms"]}},
    {"name": "update_article", "description": "原地更新已发布的文章（不是新发一篇）",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "integer"}, "platforms": {"type": "array", "items": {"type": "string"}}},
         "required": ["id"]}},
    {"name": "sync_pending", "description": "把所有改动同步到已发布平台",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "refresh_platform", "description": "抓取平台上已有文章列表入库（AI 才能看见账号里有什么）",
     "inputSchema": {"type": "object", "properties": {"platform": {"type": "string"}}, "required": ["platform"]}},
    {"name": "check_account", "description": "检查平台登录态是否还有效",
     "inputSchema": {"type": "object", "properties": {"platform": {"type": "string"}}, "required": ["platform"]}},
    {"name": "ai_write", "description": "AI 写一篇新文章并入库，可选顺手发布到平台",
     "inputSchema": {"type": "object", "properties": {
         "topic": {"type": "string"}, "style": {"type": "string"},
         "words": {"type": "integer"}, "tags_hint": {"type": "string"},
         "publish_to": {"type": "array", "items": {"type": "string"}}}, "required": ["topic"]}},
    {"name": "ai_rewrite", "description": "AI 按指令改写已有文章（改完自动标记待同步）",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "integer"}, "instruction": {"type": "string"},
         "publish_to": {"type": "array", "items": {"type": "string"}}}, "required": ["id", "instruction"]}},
    {"name": "ai_polish", "description": "AI 润色文章：修错别字、统一代码块语言、理顺结构",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}},
]


def call_tool(name, args):
    if name == "hub_status":
        return hub.status()
    if name == "list_articles":
        return hub.list(args.get("status"), args.get("limit", 100))
    if name == "get_article":
        return hub.get(args["id"])
    if name == "create_article":
        return {"id": hub.create(**args)}
    if name == "edit_article":
        i = args.pop("id")
        ok, pend = hub.edit(i, **args)
        return {"ok": ok, "pending_sync": pend}
    if name == "publish_article":
        return hub.publish(args["id"], args["platforms"], draft_only=args.get("draft_only", False))
    if name == "update_article":
        return hub.update(args["id"], args.get("platforms"))
    if name == "sync_pending":
        return hub.sync_pending()
    if name == "refresh_platform":
        return hub.refresh(args["platform"])
    if name == "check_account":
        return {"platform": args["platform"], "logined": hub.check(args["platform"])}
    if name == "ai_write":
        return hub.ai_write(args["topic"], args.get("style", ""), args.get("words", 2000),
                            args.get("tags_hint", ""), args.get("publish_to"))
    if name == "ai_rewrite":
        return hub.ai_rewrite(args["id"], args["instruction"], args.get("publish_to"))
    if name == "ai_polish":
        return hub.ai_polish(args["id"])
    raise ValueError(f"未知工具: {name}")


def reply(req_id, result):
    msg = {"jsonrpc": "2.0", "id": req_id, "result": result}
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        method, rid = req.get("method"), req.get("id")

        if method == "initialize":
            reply(rid, {"protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "ai-content-hub", "version": "0.1.0"}})
        elif method == "tools/list":
            reply(rid, {"tools": TOOLS})
        elif method == "tools/call":
            params = req.get("params", {})
            try:
                out = call_tool(params.get("name"), params.get("arguments", {}))
                reply(rid, {"content": [{"type": "text",
                                         "text": json.dumps(out, ensure_ascii=False, default=str)}]})
            except Exception as e:
                reply(rid, {"content": [{"type": "text", "text": f"ERROR: {e}"}],
                            "isError": True})
        elif method and method.startswith("notifications/"):
            continue  # 通知不用回
        elif rid is not None:
            reply(rid, {})


if __name__ == "__main__":
    main()
