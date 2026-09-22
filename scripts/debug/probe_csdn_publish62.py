# -*- coding: utf-8 -*-
"""CSDN 发布探针 62：勾选目录后，找正确的发布按钮并监听 API。"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
from core.adapters.csdn import CSDNAdapter

ad = CSDNAdapter()
br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
assert ad.check_auth(page), "CSDN 未登录"
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
}""", "【CSDN 决定 62】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(8)

# 1) 用 JS 点击 checkbox（上一轮验证 JS click 能写 hidden categories）
page.evaluate("""() => {
    const inps = document.querySelectorAll('input.tag__option-chk');
    for (const c of inps) { if (c.value === '后端与架构设计') {
        const lbl = c.closest('label');
        if (lbl) lbl.click(); else c.click();
    } }
}""")
time.sleep(1)
cat = page.evaluate("() => { const c = document.querySelector('.tag__box input[type=hidden][name=categories]'); return c ? c.value : null; }")
print(f"\n[1] 目录 categories = {cat!r}")

# 2) 填摘要
try:
    page.locator('textarea.el-textarea__inner').first.fill("Python 协程原理与实战")
    print("[2] 摘要已填")
except Exception as e:
    print(f"[2] 摘要失败: {e}")
time.sleep(1)

# 3) dump 弹窗当前所有"可见"按钮（找正确的发布按钮）
js = """() => {
  const modal = document.querySelector('.publish-article-modal');
  if (!modal) return {noModal:true};
  const btns = Array.from(modal.querySelectorAll('button')).map(b => ({
    text: (b.innerText||b.title||'').trim().slice(0,40),
    cls: String(b.className||'').slice(0,60),
    visible: b.offsetParent !== null && window.getComputedStyle(b).display !== 'none',
    disabled: b.disabled,
    top: String(b.getBoundingClientRect().top|0),
    left: String(b.getBoundingClientRect().left|0),
    w: b.offsetWidth, h: b.offsetHeight
  })).filter(b => b.visible && b.text.length > 0);
  // 也找 footer 区域
  const footer = modal.querySelector('[class*=footer], [class*=button-bar], .modal__footer');
  const footerTxt = footer ? footer.innerText.slice(0,200) : 'no footer';
  return {btns, footerTxt, footerCls: footer ? String(footer.className||'').slice(0,60) : ''};
}"""
d = page.evaluate(js)
print(f"\n[3] 弹窗可见按钮:")
for b in d.get("btns", []):
    print(f"  text={b['text']!r:40s} cls={b['cls']!r:40s} dis={b['disabled']} at=({b['left']},{b['top']}) {b['w']}x{b['h']}")
print(f"  footer text: {d.get('footerTxt')!r}")

# 4) 找"发布文章"按钮的完整 class（之前认为 .btn-b-red.ml16，可能变了）
pub_info = page.evaluate("""() => {
  const modal = document.querySelector('.publish-article-modal');
  if (!modal) return null;
  const all = Array.from(modal.querySelectorAll('button, [class*=btn]'));
  const pub = all.filter(b => (b.innerText||'').includes('发布') || (b.className||'').includes('btn-b'));
  return pub.map(b => ({text:(b.innerText||'').trim().slice(0,30), cls:String(b.className||''),
    visible: b.offsetParent!==null, w:b.offsetWidth, h:b.offsetHeight,
    rect: (r=>({x:r.x|0,y:r.y|0,w:r.width|0,h:r.height|0}))(b.getBoundingClientRect())}));
}""")
print(f"\n[4] 含'发布'/btn-b 的元素: {json.dumps(pub_info, ensure_ascii=False)}")

# 5) 监听 API，用正确的按钮点击发布
captured = []
def on_resp(resp):
    try:
        u = resp.url
        if "csdn" not in u or "eva2" in u:
            return
        if resp.request.method in ("POST", "PUT"):
            body = None
            try: body = resp.request.post_data
            except Exception: pass
            txt = None
            try: txt = resp.text()[:800]
            except Exception: txt = "(no)"
            captured.append({"method": resp.request.method, "url": u, "status": resp.status,
                              "body": (body or "")[:400], "resp": txt})
    except Exception:
        pass
page.on("response", on_resp)

print("\n[5] 逐个尝试可见的发布按钮")
time.sleep(1)
# 重新取按钮列表（DOM 可能刷新）
btns_now = page.evaluate("""() => {
  const modal = document.querySelector('.publish-article-modal');
  if (!modal) return [];
  return Array.from(modal.querySelectorAll('button')).map((b,i) => ({i,
    text:(b.innerText||'').trim().slice(0,30),
    cls:String(b.className||'').slice(0,50),
    visible: b.offsetParent!==null,
    w:b.offsetWidth, h:b.offsetHeight})).filter(b=>b.visible && b.w>0);
}""")
print(f"  当前可见按钮: {json.dumps(btns_now, ensure_ascii=False)}")

for b in btns_now:
    if "发布" in b["text"] and ("btn-b" in b["cls"] or b["w"] > 0):
        print(f"  -> 点击按钮 i={b['i']} text={b['text']!r} cls={b['cls']!r}")
        try:
            page.evaluate("""(i) => {
                const modal = document.querySelector('.publish-article-modal');
                const bs = Array.from(modal.querySelectorAll('button'));
                if (bs[i]) bs[i].click();
            }""", b["i"])
            print("    JS click OK")
        except Exception as e:
            print(f"    点击失败: {e}")
        time.sleep(12)
        break

print(f"\n--- 捕获 {len(captured)} 个 csdn POST/PUT ---")
for c in captured:
    print(f"\n  [{c['status']}] {c['method']} {c['url']}")
    if c['body']: print(f"    req: {c['body'][:250]}")
    print(f"    resp: {c['resp']}")

print(f"\nURL: {page.url}")
if "articleId=" in page.url:
    aid = page.url.split("articleId=")[-1].split("&")[0]
    print(f"*** 发布成功 articleId = {aid} ***")

try:
    page.screenshot(path="data/csdn_publish62.png")
    print("\n截图: data/csdn_publish62.png")
except Exception:
    pass
br.close()
