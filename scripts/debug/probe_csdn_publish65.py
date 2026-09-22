# -*- coding: utf-8 -*-
"""CSDN 发布探针 65：抓 userstatus 响应体 + 长等待 + 验证码检测。"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser, CaptchaPolicy
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
}""", "【CSDN 攻坚 65】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(10)

# 填三件套
page.evaluate("""() => {
    const inps = document.querySelectorAll('input.tag__option-chk');
    for (const c of inps) { if (c.value === '后端与架构设计') {
        const lbl = c.closest('label'); if (lbl) lbl.click(); else c.click(); } }
}""")
time.sleep(1)
page.evaluate("""(t) => {
    const ta = document.querySelector('textarea.el-textarea__inner');
    if (ta) { const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
      s.call(ta, t); ta.dispatchEvent(new Event('input',{bubbles:true})); }
}""", "Python 协程原理与实战：从 asyncio 到生产架构")
time.sleep(1)
cat = page.evaluate("() => document.querySelector('.tag__box input[type=hidden][name=categories]')?.value")
print(f"[pre] categories={cat!r}")

# 监听全部响应（重点抓 userstatus 的响应体）
events = []
def on_resp(resp):
    try:
        u = resp.url
        if "eva2" in u:
            return
        if resp.request.method in ("POST", "PUT"):
            try:
                txt = resp.text()[:1200]
            except Exception:
                txt = "(resp body unreadable)"
            events.append({"t": time.time(), "url": u, "status": resp.status,
                           "body": (resp.request.post_data or "")[:300], "resp": txt})
    except Exception:
        pass
page.on("response", on_resp)

print("\n[click] JS 点击发布按钮，随后轮询 30s")
page.evaluate("() => document.querySelector('button.btn-b-red.ml16')?.click()")
t0 = time.time()
result = None
while time.time() - t0 < 30:
    time.sleep(2)
    u = page.url
    if "articleId=" in u or "/p/" in u:
        result = f"URL 变了: {u}"
        break
    # 弹窗是否消失
    modal_open = page.evaluate("() => !!document.querySelector('.modal__button-bar')")
    if not modal_open:
        result = f"弹窗已关闭, URL: {u}"
        break
    # 验证码检测
    kind = CaptchaPolicy.detect(page)
    if kind:
        result = f"出现验证码: {kind}"
        break
print(f"\n结果: {result or '30s 内无变化'}")

print(f"\n--- 捕获 {len(events)} 个 POST/PUT 响应 ---")
for e in events:
    print(f"\n  [{e['status']}] {e['url']}")
    if e['body']: print(f"    req: {e['body']}")
    print(f"    resp: {e['resp']}")

if not result or "验证码" in str(result):
    txt = page.evaluate("""() => ({
        modalText: (document.querySelector('.modal__inner-2')||{}).innerText?.slice(0,600),
        errs: Array.from(document.querySelectorAll('[class*=error], [class*=tip], .el-message, [class*=warning]'))
          .map(e => (e.innerText||'').trim()).filter(t => t && t.length>1 && t.length < 120).slice(0, 15)
    })""")
    print(f"\n弹窗现状: {json.dumps(txt, ensure_ascii=False)}")

try:
    page.screenshot(path="data/csdn_publish65.png")
    print("\n截图: data/csdn_publish65.png")
except Exception:
    pass
br.close()
