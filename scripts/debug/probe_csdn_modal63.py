# -*- coding: utf-8 -*-
"""CSDN 弹窗结构探针 63：确认 .btn-publish 后弹窗是否真的打开，发布按钮到底在哪。"""
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
}""", "【CSDN 探针 63】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)

# 点 .btn-publish
pb = page.query_selector('.btn-publish')
print(f"\n.btn-publish 存在={pb is not None} 可见={pb.is_visible() if pb else 'n/a'}")
pb.click(timeout=8000)
time.sleep(10)  # 等弹窗完全渲染

# 全页面 dump：哪些 class 含 modal 的元素，哪些可见
js = """() => {
  const all = Array.from(document.querySelectorAll('[class*=modal], [class*=Modal], .el-dialog, [class*=publish]'));
  const vis = all.filter(e => e.offsetParent !== null && e.offsetWidth > 0 && window.getComputedStyle(e).display !== 'none');
  return vis.map(e => ({
    tag: e.tagName, cls: String(e.className||'').slice(0,80),
    w: e.offsetWidth, h: e.offsetHeight,
    top: (e.getBoundingClientRect().top|0),
    text: (e.innerText||'').trim().slice(0,80)
  }));
}"""
d = page.evaluate(js)
print(f"\n=== 页面可见的 modal/publish/dlg 元素 ({len(d)}) ===")
for x in d:
    print(f"  <{x['tag']}> {x['cls']!r} {x['w']}x{x['h']} @top={x['top']} text={x['text']!r}")

# 当前页面所有可见 button
js2 = """() => {
  const bs = Array.from(document.querySelectorAll('button')).filter(b =>
    b.offsetParent !== null && b.offsetWidth > 0 && (b.innerText||'').trim().length > 0);
  return bs.map(b => ({text:(b.innerText||'').trim().slice(0,30),
    cls:String(b.className||'').slice(0,50), top:b.getBoundingClientRect().top|0,
    w:b.offsetWidth}));
}"""
btns = page.evaluate(js2)
print(f"\n=== 页面所有可见 button ({len(btns)}) ===")
for b in btns:
    print(f"  text={b['text']!r:30s} cls={b['cls']!r:45s} @top={b['top']} w={b['w']}")

# 找"发布文章"具体元素（可能不是 button.btn-b-red.ml16）
pub_all = page.evaluate("""() => {
  const all = Array.from(document.querySelectorAll('*'));
  return all.filter(e => (e.innerText||'').trim() === '发布文章' && e.children.length === 0)
    .map(e => ({tag:e.tagName, cls:String(e.className||'').slice(0,60),
      visible: e.offsetParent!==null, w:e.offsetWidth,
      rect:(r=>({x:r.x|0,y:r.y|0}))(e.getBoundingClientRect())}));
}""")
print(f"\n=== 文本恰为'发布文章'的元素: {json.dumps(pub_all, ensure_ascii=False)}")

try:
    page.screenshot(path="data/csdn_modal63.png")
    print("\n截图: data/csdn_modal63.png")
except Exception:
    pass
br.close()
