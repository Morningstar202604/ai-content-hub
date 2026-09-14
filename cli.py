# -*- coding: utf-8 -*-
"""命令行入口：不想开服务时，用这个管一切。"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.service import Hub


def main():
    ap = argparse.ArgumentParser("hub", description="AI 内容中台命令行")
    ap.add_argument("--headed", action="store_true", help="显示浏览器窗口（登录/排错时用）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("login", help="扫码/过验证登录（首次必须，之后长期有效）")
    p.add_argument("--platform", required=True)
    p.add_argument("--account", default="default")
    p.add_argument("--timeout", type=int, default=600, help="等登录的秒数")
    p.add_argument("--on-captcha", default="handoff", choices=["handoff", "skip", "abort"],
                   help="遇到验证码：handoff=暂停交人工（默认）/ abort=直接放弃")

    p = sub.add_parser("check", help="检查登录态")
    p.add_argument("--platform", required=True)
    p.add_argument("--account", default="default")

    p = sub.add_parser("diagnose", help="这个平台怎么接、验证码怎么过")
    p.add_argument("--platform", required=True)

    p = sub.add_parser("solve-captcha", help="打开页面就地处理验证码（半自动+人工）")
    p.add_argument("--platform", required=True)
    p.add_argument("--account", default="default")
    p.add_argument("--wait", type=int, default=180, help="等人工的秒数")

    p = sub.add_parser("bootstrap-cnblogs",
                       help="浏览器登录博客园并自动抠出 MetaWeblog 令牌写进 config.json")
    p.add_argument("--username", required=True, help="博客园登录用户名/邮箱")
    p.add_argument("--password", required=True, help="登录密码")
    p.add_argument("--account", default="default")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--on-captcha", default="handoff", choices=["handoff", "abort"])

    p = sub.add_parser("import", help="导入本地 Markdown")
    p.add_argument("--path", required=True)
    p.add_argument("--tags", default="")

    p = sub.add_parser("create", help="新建文章")
    p.add_argument("--title", required=True)
    p.add_argument("--content", default="")
    p.add_argument("--tags", default="")

    p = sub.add_parser("publish", help="发布到平台")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--platforms", required=True, help="逗号分隔，如 juejin,csdn")
    p.add_argument("--draft", action="store_true", help="只发草稿箱")

    p = sub.add_parser("update", help="原地更新已发布文章")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--platforms", default="")

    p = sub.add_parser("sync", help="把所有改动同步到已发布平台")

    p = sub.add_parser("refresh", help="抓取平台文章列表入库")
    p.add_argument("--platform", required=True)

    p = sub.add_parser("ai-write", help="AI 写一篇并入库")
    p.add_argument("--topic", required=True)
    p.add_argument("--style", default="")
    p.add_argument("--words", type=int, default=2000)
    p.add_argument("--tags", default="", dest="tags_hint")
    p.add_argument("--publish", default="", help="写完顺手发到这些平台，逗号分隔")

    p = sub.add_parser("ai-rewrite", help="AI 改写已有文章")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--instruction", required=True)
    p.add_argument("--publish", default="")

    p = sub.add_parser("ai-polish", help="AI 润色文章")
    p.add_argument("--id", type=int, required=True)

    sub.add_parser("status", help="中台总览")
    sub.add_parser("serve", help="启动 REST API 服务")

    a = ap.parse_args()
    hub = Hub(headless=not a.headed)

    if a.cmd == "login":
        ok, msg = hub.login(a.platform, a.account, a.timeout, a.on_captcha)
        print(("✓ " if ok else "✗ ") + msg)
    elif a.cmd == "check":
        print("✓ 已登录" if hub.check(a.platform, a.account) else "✗ 未登录，跑 login")
    elif a.cmd == "diagnose":
        print(json.dumps(hub.diagnose(a.platform), ensure_ascii=False, indent=2))
    elif a.cmd == "solve-captcha":
        print(json.dumps(hub.solve_captcha(a.platform, a.account, a.wait),
                         ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "bootstrap-cnblogs":
        r = hub.bootstrap_cnblogs(a.username, a.password, a.account,
                                  a.timeout, a.on_captcha)
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "import":
        print("导入成功，文章 ID =", hub.import_md(a.path, tags=a.tags))
    elif a.cmd == "create":
        print("文章 ID =", hub.create(a.title, a.content, tags=a.tags, source="human"))
    elif a.cmd == "publish":
        print(json.dumps(hub.publish(a.id, a.platforms.split(","), draft_only=a.draft),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "update":
        plats = a.platforms.split(",") if a.platforms else None
        print(json.dumps(hub.update(a.id, plats), ensure_ascii=False, indent=2))
    elif a.cmd == "sync":
        print(json.dumps(hub.sync_pending(), ensure_ascii=False, indent=2))
    elif a.cmd == "refresh":
        print(json.dumps(hub.refresh(a.platform), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "ai-write":
        pub = a.publish.split(",") if a.publish else None
        print(json.dumps(hub.ai_write(a.topic, a.style, a.words, a.tags_hint, pub),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "ai-rewrite":
        pub = a.publish.split(",") if a.publish else None
        print(json.dumps(hub.ai_rewrite(a.id, a.instruction, pub),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "ai-polish":
        print(json.dumps(hub.ai_polish(a.id), ensure_ascii=False, indent=2))
    elif a.cmd == "status":
        print(json.dumps(hub.status(), ensure_ascii=False, indent=2))
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("server.api:app", host="127.0.0.1", port=8800, reload=False)


if __name__ == "__main__":
    main()
