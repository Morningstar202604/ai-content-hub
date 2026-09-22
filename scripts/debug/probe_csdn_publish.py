# -*- coding: utf-8 -*-
"""CSDN 发布流程探针：精确点 .btn-b-red，抓 publish API。"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
import core.adapters.csdn
from core.adapters.csdn import CSDNAdapter

ad = CSDNAdapter()
br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()

if not ad.check_auth(page):
    print("CSDN 未登录")
    br.close()
    sys.exit(1)
print("登录 OK")

page.goto(ad.new_url, timeout=60000, wait_until="domcontentloaded")
try:
    page.wait_for_selector("pre.editor__inner[contenteditable=true], .CodeMirror",
                           timeout=30000)
except Exception:
    pass
time.sleep(3)

content_md = Path("data/test_article.md").read_text(encoding="utf-8")
page.evaluate("""(t) => {
    const input = document.querySelector('.article-bar__title--input');
    if (input) {
        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        s.call(input, t);
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new Event('change', {bubbles: true}));
    }
}""", "【CSDN 测试 3】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)

# 开弹窗
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(5)

# 验证标题
title_val = page.evaluate("() => document.querySelector('.article-bar__title--input') ? document.querySelector('.article-bar__title--input').value : ''")
print(f"标题: {title_val!r}")
body_len = page.evaluate("() => { const ed = document.querySelector('pre.editor__inner[contenteditable=true]'); return ed ? ed.innerText.length : 0; }")
print(f"正文长度: {body_len}")

all_reqs = []


def on_req(req):
    u = req.url
    if "csdn" not in u:
        return
    m = req.method
    if m not in ("POST", "PUT", "GET"):
        return
    body = None
    try:
        if m in ("POST", "PUT"):
            body = req.post_data
    except Exception:
        body = ""
    all_reqs.append({"method": m, "url": u, "body": body, "ts": time.time()})


page.on("request", on_req)

print("\n=== 点 .btn-b-red (发布文章) ===")
all_reqs.clear()
red_btn = page.query_selector('.btn-b-red')
if red_btn:
    print(f"  .btn-b-red visible={red_btn.is_visible()}")
    red_btn.click(timeout=8000)
    print("  点击 OK")
else:
    print("  没找到 .btn-b-red，用 text=发布文章")
    page.click("text=发布文章", timeout=8000)
time.sleep(12)

print(f"\nURL: {page.url}")

print(f"\n--- 抓到 {len(all_reqs)} 个请求 ---")
interesting = []
for r in all_reqs:
    if "eva2" in r["url"]:
        continue
    b = r.get("body") or ""
    print(f"  {r['method']} {r['url']}")
    if b:
        print(f"      body: {b[:250]}")
    if any(k in r["url"] for k in ("publish", "article", "commit", "articleDetail")):
        interesting.append(r)

if not interesting:
    print("  （无 publish/article/commit 相关请求）")

try:
    page.screenshot(path="data/csdn_after_publish.png")
    print("\n截图: data/csdn_after_publish.png")
except Exception:
    pass

br.close()
