# -*- coding: utf-8 -*-
"""CSDN 发布探针 68：标签面板不关闭，直接 JS 点发布（修 _select_tag 关错弹窗的 bug）。"""
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
}""", "【CSDN 攻坚 68】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(10)

# ===== 错误钩子 =====
page.evaluate("""() => {
    window.__errors = [];
    window.addEventListener('error', e => window.__errors.push('ERR:' + String(e.message).slice(0,150)));
    window.addEventListener('unhandledrejection', e => window.__errors.push('REJ:' + String(e.reason && e.reason.message || e.reason).slice(0,150)));
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

# 3) 标签：打开面板 → dump 面板结构 → 点 Python → 不关面板
modal_scope = '.modal__inner-2'
try:
    # 限定在弹窗内找"添加文章标签"按钮（跳过"新建分类专栏"）
    btns = page.locator(f'{modal_scope} button.tag__btn-tag')
    n = btns.count()
    print(f"[tag] 弹窗内 tag__btn-tag 按钮数: {n}")
    target_btn = None
    for i in range(n):
        t = btns.nth(i).inner_text().strip()
        print(f"    btn[{i}] text={t!r}")
        if "添加文章标签" in t:
            target_btn = i
    if target_btn is not None:
        btns.nth(target_btn).click(timeout=5000)
        time.sleep(4)
    # dump 面板里的 el-tag
    tags = page.locator(f'{modal_scope} span.el-tag')
    nt = tags.count()
    print(f"[tag] 面板 el-tag 数: {nt}")
    clicked = False
    for i in range(nt):
        t = tags.nth(i).inner_text().strip()
        if t.lower() == "python":
            tags.nth(i).click(timeout=5000)
            clicked = True
            print(f"    已点击 el-tag[{i}] 'Python'")
            break
    if not clicked and nt > 0:
        tags.nth(0).click(timeout=5000)
        print(f"    没找到 Python，点了第 0 个: {tags.nth(0).inner_text().strip()!r}")
    time.sleep(2)
except Exception as e:
    print(f"[tag] 流程异常: {e}")

# 验证三件套状态
state = page.evaluate("""() => ({
    categories: document.querySelector('.tag__box input[type=hidden][name=categories]')?.value ?? null,
    summary: document.querySelector('textarea.el-textarea__inner')?.value?.slice(0,40) ?? null,
    modalOpen: !!document.querySelector('.modal__button-bar'),
    tagChips: (document.querySelector('.tag__item-list')?.innerText || '').trim().slice(0,80)
})""")
print(f"\n[state] {json.dumps(state, ensure_ascii=False)}")

# 4) 注入 fetch 钩子
page.evaluate("""() => {
    window.__net = [];
    const of = window.fetch;
    window.fetch = function(...args) {
        const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
        const opt = args[1] || {};
        window.__net.push({m: opt.method || 'GET', u: String(url).slice(0, 200),
                           b: typeof opt.body === 'string' ? opt.body.slice(0, 300) : ''});
        return of.apply(this, args);
    };
    const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m, u) { this.__m = m; this.__u = u; return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function(b) {
        window.__net.push({m: this.__m, u: String(this.__u).slice(0, 200),
                           b: typeof b === 'string' ? b.slice(0, 300) : ''});
        return os.apply(this, arguments);
    };
}""")

# 5) JS 点发布（不关标签面板），高频轮询
print("\n[click] JS 点击发布按钮…")
r = page.evaluate("() => { const b = document.querySelector('button.btn-b-red.ml16'); if (b) { b.click(); return 'ok'; } return 'no button'; }")
print(f"    click: {r}")
toasts = []
t0 = time.time()
published = False
while time.time() - t0 < 25:
    batch = page.evaluate("""() => ({
        msgs: Array.from(document.querySelectorAll('.el-message, .el-notification'))
          .map(e => (e.innerText||'').trim()).filter(t => t && t.length < 100),
        url: location.href,
        modalOpen: !!document.querySelector('.modal__button-bar')
    })""")
    for m in batch["msgs"]:
        if m not in toasts:
            toasts.append(m)
            print(f"  [toast] {m!r}")
    if "articleId=" in batch["url"] or "/p/" in batch["url"]:
        print(f"  *** 发布成功! URL: {batch['url']} ***")
        published = True
        break
    if not batch["modalOpen"] and time.time() - t0 > 4:
        print(f"  弹窗已关闭, URL: {batch['url']}")
        break
    time.sleep(0.4)

print(f"\n最终 URL: {page.url}")
aid = ""
if "articleId=" in page.url:
    aid = page.url.split("articleId=")[-1].split("&")[0]
    print(f"*** articleId = {aid} ***")

net = [n for n in page.evaluate("() => window.__net || []")
       if not any(k in n['u'] for k in ("eva2", "r.png", "retcode", "hm.baidu"))]
print(f"\n=== 网络调用 {len(net)} 个 ===")
for n in net:
    print(f"  {n['m']} {n['u']}")
    if n['b']: print(f"        {n['b'][:200]}")
errs = page.evaluate("() => window.__errors || []")
print(f"\nJS 错误: {errs[:8]}")

try:
    page.screenshot(path="data/csdn_publish68.png")
except Exception:
    pass
br.close()
