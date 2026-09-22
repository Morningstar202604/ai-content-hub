# -*- coding: utf-8 -*-
"""CSDN 目录 dropdown 展开 + 真实点击 label 探针。"""
import sys, time
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
}""", "【CSDN 探针 60】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(8)

# 1) 探查 .tag__box 里有哪些可交互子元素（按钮/dropdown 触发器）
js = """() => {
  const box = document.querySelector('.tag__box');
  if (!box) return {noBox: true};
  const el = (n) => ({tag:n.tagName, cls:String(n.className||'').slice(0,60),
    text:(n.innerText||n.title||'').trim().slice(0,30),
    vis: window.getComputedStyle(n).display,
    bb: (()=>{const r=n.getBoundingClientRect();return r.width>0&&r.height>0;})()});
  const kids = Array.from(box.querySelectorAll('button, .tag__item, [class*=tag], .el-input, .el-dropdown, .el-select')).slice(0,30);
  return {
    boxText: box.innerText.trim().slice(0,200),
    boxHtml: box.outerHTML.slice(0, 1500),
    kids: kids.map(el)
  };
}"""
print("\n=== .tag__box 结构 ===")
print(page.evaluate(js))

# 2) 找 tag__options-content 的可见性 + 触发它展开的元素
js2 = """() => {
  const content = document.querySelector('.tag__options-content');
  const st = content ? window.getComputedStyle(content) : null;
  return content ? {disp: st.display, vis: st.visibility, pos: st.position,
    w: content.offsetWidth, h: content.offsetHeight,
    parentDisp: window.getComputedStyle(content.parentElement).display} : {none:true};
}"""
print("\n=== .tag__options-content 状态 ===")
print(page.evaluate(js2))

# 3) 尝试点击 .tag__box 里能触发 dropdown 的元素（按钮/输入框）
try:
    # 尝试各种可能的触发器
    triggers = ['.tag__box button', '.tag__box .el-input', '.tag__box .el-dropdown',
                '.tag__box input[type=hidden]', '.tag__box .tag__item', '.tag__box [class*=caret]',
                '.tag__box .el-select', '.tag__box input[type=text]', '.tag__box input']
    hit = []
    for sel in triggers:
        n = page.locator(sel).count()
        if n > 0:
            hit.append(f"{sel} -> {n}")
    print("\n=== 候选触发器 ===")
    for h in hit: print("  " + h)
except Exception as e:
    print(f"触发器探查错: {e}")

# 4) 强制展开 .tag__options-content，点击 label 看 checked 变化
try:
    page.evaluate("""() => {
        const c = document.querySelector('.tag__options-content');
        if (c) c.style.display = 'block';
    }""")
    time.sleep(0.5)
    # 现在 label 应该有可见尺寸
    label = page.locator("label.tag__option-label:has(input[value='后端与架构设计'])").first
    bb = label.bounding_box()
    print(f"\n后端与架构设计 label bb = {bb}")
    if bb and bb['width'] > 0:
        before = page.evaluate("() => { const c = document.querySelector('input.tag__option-chk[value=后端与架构设计]'); return c ? c.checked : null; }")
        label.click(timeout=5000)
        time.sleep(1)
        after = page.evaluate("() => { const c = document.querySelector('input.tag__option-chk[value=后端与架构设计]'); return c ? c.checked : null; }")
        print(f"label 点击: 前 checked={before}  后 checked={after}")
except Exception as e:
    print(f"label 点击错: {e}")

try:
    page.screenshot(path="data/csdn_checkbox_probe60.png")
    print("\n截图: data/csdn_checkbox_probe60.png")
except Exception:
    pass
br.close()
