# -*- coding: utf-8 -*-
"""抓掘金 editor 页面的 JS bundle，找 publish 调用点。"""
import sys, time, json, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser

br = BuiltinBrowser("juejin", "default", headless=True)
page = br.start().new_page()

loaded_js = []


def on_resp(resp):
    u = resp.url
    ct = resp.headers.get("content-type", "")
    if "juejin" not in u:
        return
    if "text/javascript" not in ct and "application/javascript" not in ct:
        return
    try:
        body = resp.text()
        loaded_js.append((u, body))
    except Exception:
        pass


page.on("response", on_resp)
page.goto("https://juejin.cn/editor/drafts/new", timeout=60000,
          wait_until="networkidle")
time.sleep(3)
print(f"加载了 {len(loaded_js)} 个 JS")
for u, b in loaded_js:
    print(f"  {u} ({len(b)} bytes)")

print("\n--- 在 bundle 里搜 publish 关键字 ---")
for u, b in loaded_js:
    hits = list(re.finditer(
        r'article/publish|article_publish|articlePublish|sync_to_org|'
        r'column_ids|article_draft/update', b))
    if hits:
        print(f"\n{u}: {len(hits)} 处命中")
        for m in hits[:15]:
            s = max(0, m.start() - 200)
            e = min(len(b), m.end() + 400)
            snippet = b[s:e]
            print(f"  @{m.start()}: {snippet[:600]}")
            print()

br.close()
