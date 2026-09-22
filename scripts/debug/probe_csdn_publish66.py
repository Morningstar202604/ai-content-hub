# -*- coding: utf-8 -*-
"""CSDN 发布探针 66：页面内 fetch/XHR 全钩子 + 验证码 DOM 专查。"""
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
}""", "【CSDN 攻坚 66】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(10)

# 三件套
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
}""", "Python 协程原理与实战")
time.sleep(1)

# ===== 页面内注入 fetch/XHR 钩子 =====
page.evaluate("""() => {
    window.__net = [];
    const of = window.fetch;
    window.fetch = function(...args) {
        const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
        const opt = args[1] || {};
        window.__net.push({k: 'fetch', m: opt.method || 'GET', u: String(url).slice(0, 200),
                           b: typeof opt.body === 'string' ? opt.body.slice(0, 300) : ''});
        return of.apply(this, args);
    };
    const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m, u) { this.__m = m; this.__u = u; return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function(b) {
        window.__net.push({k: 'xhr', m: this.__m, u: String(this.__u).slice(0, 200),
                           b: typeof b === 'string' ? b.slice(0, 300) : ''});
        return os.apply(this, arguments);
    };
}""")

print("\n[click] 点击发布按钮，轮询 35s")
page.evaluate("() => document.querySelector('button.btn-b-red.ml16')?.click()")
t0 = time.time()
stop = False
while time.time() - t0 < 35:
    time.sleep(3)
    u = page.url
    if "articleId=" in u:
        print(f"  URL 变了: {u}"); stop = True; break
    if not page.evaluate("() => !!document.querySelector('.modal__button-bar')"):
        print(f"  弹窗关闭, URL: {u}"); stop = True; break

# ===== 验证码 DOM 专查 =====
cap = page.evaluate("""() => {
  const out = {iframes: [], captchaEls: []};
  for (const f of document.querySelectorAll('iframe')) {
    out.iframes.push({src: String(f.src||'').slice(0,150), w: f.offsetWidth, h: f.offsetHeight,
      vis: f.offsetParent !== null});
  }
  const sels = ['#aliyunCaptcha', '[class*=captcha]', '[class*=Captcha]', '[id*=captcha]',
    '.nc-container', '[class*=nc_]', '[class*=slider]', '[class*=verify]'];
  const seen = new Set();
  for (const sel of sels) {
    for (const e of document.querySelectorAll(sel)) {
      if (seen.has(e)) continue; seen.add(e);
      const r = e.getBoundingClientRect();
      out.captchaEls.push({sel, tag: e.tagName, cls: String(e.className||'').slice(0,60),
        w: e.offsetWidth, h: e.offsetHeight, vis: e.offsetParent !== null,
        rect: {x: r.x|0, y: r.y|0}});
    }
  }
  return out;
}""")
print(f"\n=== iframes ({len(cap['iframes'])}) ===")
for f in cap['iframes']: print(f"  {f}")
print(f"\n=== captcha 相关元素 ({len(cap['captchaEls'])}) ===")
for e in cap['captchaEls'][:25]: print(f"  {e}")

# ===== 页面内网络钩子记录 =====
net = page.evaluate("() => window.__net || []")
print(f"\n=== 页面内捕获 {len(net)} 个网络调用（点击发布后） ===")
for n in net:
    if any(k in n['u'] for k in ("eva2", "r.png", "retcode", "hm.baidu")):
        continue
    print(f"  [{n['k']}] {n['m']} {n['u']}")
    if n['b']: print(f"        body: {n['b'][:200]}")

print(f"\n最终 URL: {page.url}")

try:
    page.screenshot(path="data/csdn_publish66.png")
except Exception:
    pass
br.close()
