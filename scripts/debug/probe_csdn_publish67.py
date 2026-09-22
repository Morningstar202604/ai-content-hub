# -*- coding: utf-8 -*-
"""CSDN 发布探针 67：目录+摘要+标签全齐 + 全局错误钩子 + 高频抓 toast。"""
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
}""", "【CSDN 攻坚 67】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(10)

# ===== 错误/toast 钩子（点击前注入） =====
page.evaluate("""() => {
    window.__errors = [];
    window.addEventListener('error', e => window.__errors.push({t: 'error', msg: String(e.message).slice(0,200), src: String(e.filename||'').slice(0,80)}));
    window.addEventListener('unhandledrejection', e => window.__errors.push({t: 'rejection', msg: String(e.reason && e.reason.message || e.reason).slice(0,200)}));
}""")

# 1) 目录
page.evaluate("""() => {
    const inps = document.querySelectorAll('input.tag__option-chk');
    for (const c of inps) { if (c.value === '后端与架构设计') {
        const lbl = c.closest('label'); if (lbl) lbl.click(); else c.click(); } }
}""")
time.sleep(1)

# 2) 摘要
page.evaluate("""(t) => {
    const ta = document.querySelector('textarea.el-textarea__inner');
    if (ta) { const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
      s.call(ta, t); ta.dispatchEvent(new Event('input',{bubbles:true})); }
}""", "Python 协程原理与实战")
time.sleep(1)

# 3) 标签（复用适配器逻辑：添加文章标签 → 选 el-tag → 关面板）
tag_ok = ad._select_tag(page, "Python")
print(f"[tag] 选择结果: {tag_ok}")
time.sleep(1)
# 验证标签确实选上了（面板里选中的 el-tag 会出现在 tagList）
tag_state = page.evaluate("""() => {
    const list = document.querySelector('#tagList');
    return list ? list.innerText.trim().slice(0, 100) : '(no tagList)';
}""")
print(f"[tag] tagList 内容: {tag_state!r}")

cat = page.evaluate("() => document.querySelector('.tag__box input[type=hidden][name=categories]')?.value")
print(f"[pre] categories={cat!r}")

# 4) 点击前注入 fetch 钩子（标签面板操作可能重置了页面）
page.evaluate("""() => {
    if (window.__net) return;
    window.__net = [];
    const of = window.fetch;
    window.fetch = function(...args) {
        const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
        const opt = args[1] || {};
        window.__net.push({m: opt.method || 'GET', u: String(url).slice(0, 200),
                           b: typeof opt.body === 'string' ? opt.body.slice(0, 200) : ''});
        return of.apply(this, args);
    };
    const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m, u) { this.__m = m; this.__u = u; return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function(b) {
        window.__net.push({m: this.__m, u: String(this.__u).slice(0, 200),
                           b: typeof b === 'string' ? b.slice(0, 200) : ''});
        return os.apply(this, arguments);
    };
}""")

# 5) JS 点击发布 + 每 400ms 抓一次 toast/错误，共 20s
print("\n[click] 点击发布，高频抓 toast…")
page.evaluate("() => document.querySelector('button.btn-b-red.ml16')?.click()")
toasts = []
t0 = time.time()
published = False
while time.time() - t0 < 20:
    batch = page.evaluate("""() => {
        const msgs = Array.from(document.querySelectorAll('.el-message, .el-notification, [class*=toast], [class*=message]'))
          .map(e => (e.innerText||'').trim()).filter(t => t && t.length > 0 && t.length < 100);
        return {msgs, url: location.href,
                modalOpen: !!document.querySelector('.modal__button-bar'),
                errs: (window.__errors||[]).slice(-5)};
    }""")
    for m in batch["msgs"]:
        if m not in toasts:
            toasts.append(m)
            print(f"  [toast] {m!r}")
    if "articleId=" in batch["url"]:
        print(f"  *** 发布成功: {batch['url']} ***")
        published = True
        break
    if not batch["modalOpen"] and time.time() - t0 > 3:
        print(f"  弹窗关闭: {batch['url']}")
        published = "closed"
        break
    time.sleep(0.4)

print(f"\n最终 URL: {page.url}")
net = [n for n in page.evaluate("() => window.__net || []")
       if not any(k in n['u'] for k in ("eva2", "r.png", "retcode", "hm.baidu"))]
print(f"=== 页面内网络调用 {len(net)} 个 ===")
for n in net:
    print(f"  {n['m']} {n['u']}")
    if n['b']: print(f"        {n['b'][:180]}")
errs = page.evaluate("() => window.__errors || []")
print(f"\n=== JS 错误 {len(errs)} 个 ===")
for e in errs[:10]: print(f"  {e}")

try:
    page.screenshot(path="data/csdn_publish67.png")
except Exception:
    pass
br.close()
