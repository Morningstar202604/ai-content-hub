# -*- coding: utf-8 -*-
"""CSDN 发布最终探针 64：JS click checkbox label + JS click 红色发布按钮，抓 API。"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
from core.adapters.csdn import CSDNAdapter

ad = CSDNAdapter()
br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
assert ad.check_auth(page)
print("登录 OK")

page.goto(ad.new_url, timeout=60000, wait_until="domcontentloaded")
try:
    page.wait_for_selector("pre.editor__inner[contenteditable=true], .CodeMirror", timeout=30000)
except Exception:
    pass
time.sleep(3)
content_md = Path("data/test_article.md").read_text(encoding="utf-8")
page.evaluate("""(t) => {
    const input = document.querySelector('.article-bar__title--input');
    if (input) { const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      s.call(input, t); input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true})); }
}""", "【CSDN 最终 64】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(10)

# 1) 勾选目录（JS click on label — 已验证能写 hidden categories）
page.evaluate("""() => {
    const inps = document.querySelectorAll('input.tag__option-chk');
    for (const c of inps) { if (c.value === '后端与架构设计') {
        const lbl = c.closest('label'); if (lbl) lbl.click(); else c.click(); } }
}""")
time.sleep(1)
cat = page.evaluate("() => { const c = document.querySelector('.tag__box input[type=hidden][name=categories]'); return c ? c.value : null; }")
print(f"[1] 目录 categories = {cat!r}")

# 2) 填摘要
page.evaluate("""(t) => {
    const ta = document.querySelector('textarea.el-textarea__inner');
    if (ta) { const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
      s.call(ta, t); ta.dispatchEvent(new Event('input',{bubbles:true})); ta.dispatchEvent(new Event('change',{bubbles:true})); }
}""", "Python 协程原理与实战：从 asyncio 到生产架构")
time.sleep(1)
summ = page.evaluate("() => { const t = document.querySelector('textarea.el-textarea__inner'); return t ? t.value : null; }")
print(f"[2] 摘要 = {summ!r}")

# 3) 监听 API（请求+响应）
captured = []
def on_req(req):
    try:
        u = req.url
        if "csdn" not in u or "eva2" in u:
            return
        if req.method in ("POST", "PUT"):
            captured.append({"method": req.method, "url": u,
                             "body": (req.post_data or "")[:500], "ts": time.time()})
    except Exception:
        pass
def on_resp(resp):
    try:
        u = resp.url
        if "csdn" not in u or "eva2" in u:
            return
        if resp.request.method in ("POST", "PUT"):
            txt = None
            try: txt = resp.text()[:900]
            except Exception: txt = "(no)"
            captured.append({"method": resp.request.method, "url": u, "status": resp.status,
                             "resp": txt, "ts": time.time(), "kind": "resp"})
    except Exception:
        pass
page.on("request", on_req)
page.on("response", on_resp)

# 4) JS 点击红色发布按钮
print("\n[4] JS 点击 button.btn-b-red.ml16")
captured.clear()
r = page.evaluate("""() => {
    const b = document.querySelector('button.btn-b-red.ml16');
    if (!b) return 'no red btn';
    b.click();
    return 'clicked, text=' + (b.innerText||'').trim();
}""")
print(f"    {r}")
time.sleep(15)

print(f"\n--- 捕获 {len(captured)} 个请求/响应 ---")
for c in captured:
    mark = "R" if c.get("kind") == "resp" else "Q"
    print(f"\n  [{mark}] {c['method']} {c['url']}")
    if c.get("status"): print(f"       status={c['status']}")
    if c.get("body"): print(f"       body: {c['body'][:300]}")
    if c.get("resp"): print(f"       resp: {c['resp']}")

print(f"\nURL: {page.url}")
aid = ""
if "articleId=" in page.url:
    aid = page.url.split("articleId=")[-1].split("&")[0]
    print(f"*** 成功 articleId = {aid} ***")
elif "/p/" in page.url:
    aid = page.url.split("/p/")[-1].split("?")[0]
    print(f"*** 成功 articleId = {aid} ***")

# 若仍失败，dump 弹窗校验文本
if not aid:
    txt = page.evaluate("""() => {
        const modal = document.querySelector('.publish-article-modal, .modal__button-bar, [class*=modal]');
        if (!modal) return 'modal 已关闭';
        const errs = Array.from(document.querySelectorAll('.el-form-item__error, [class*=error-msg], [class*=is-error]'))
          .map(e => (e.innerText||'').trim()).filter(t => t && t.length>1);
        return {modalStillOpen: !!document.querySelector('.modal__button-bar'),
                errs: errs.slice(0,20),
                footText: (document.querySelector('.modal__button-bar')||{}).innerText};
    }""")
    print(f"\n校验提示: {json.dumps(txt, ensure_ascii=False)}")

try:
    page.screenshot(path="data/csdn_publish64.png")
    print("\n截图: data/csdn_publish64.png")
except Exception:
    pass
br.close()
