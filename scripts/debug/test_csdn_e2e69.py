# -*- coding: utf-8 -*-
"""CSDN 适配器端到端发布测试（正式代码路径，headless 沙箱）。"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
from core.adapters.csdn import CSDNAdapter

ad = CSDNAdapter()
br = BuiltinBrowser("csdn", "default", headless=True)   # 沙箱无窗口
page = br.start().new_page()
assert ad.check_auth(page), "CSDN 未登录"
print("登录 OK")

article = {
    "title": "【端到端 69】Python 协程全景解析：从原理到生产实战",
    "summary": "深入解析 Python 协程的演进史、asyncio 事件循环原理与生产环境实战要点。",
    "content_md": Path("data/test_article.md").read_text(encoding="utf-8"),
}
t0 = time.time()
result = ad.publish(page, article, options={"category": "后端与架构设计",
                                            "tag_category": "Python"})
print(f"\n耗时 {time.time()-t0:.0f}s")
print("结果:", json.dumps(result, ensure_ascii=False, indent=2))

if result.get("post_id"):
    print("\n=== 验证列表接口 ===")
    arts = ad.list_articles(page, limit=5)
    for a in arts[:5]:
        print(f"  [{a['post_id']}] {a['title'][:40]}  {a['url']}")
    ok = any(a["post_id"] == result["post_id"] for a in arts)
    print(f"\n列表中找到新文章: {ok}")

br.close()
