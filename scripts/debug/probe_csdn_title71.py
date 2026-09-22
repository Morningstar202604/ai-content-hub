# -*- coding: utf-8 -*-
"""CSDN 标题注入调试探针 71：_set_title 到底哪一步失败。"""
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

# 先填正文（模拟真实流程，同时验证 Control+A 是否会误伤正文）
content_md = Path("data/test_article.md").read_text(encoding="utf-8")
ok = ad._import_md_file(page, content_md)
time.sleep(2)
blen = page.evaluate("() => document.querySelector('pre.editor__inner[contenteditable=true]')?.innerText.length || 0")
print(f"[before] 正文长度 = {blen}")

# ===== 逐步调试 _set_title =====
orig = page.evaluate("""() => {
    const input = document.querySelector('.article-bar__title--input');
    if (!input) { console.log('no input'); return 'NO_INPUT'; }
    const o = input.getAttribute('style') || '';
    input.style.cssText += '; display:block !important; position:fixed;'
        + ' top:8px; left:8px; z-index:99999; width:420px; height:32px;'
        + ' opacity:1; background:#fff; color:#000;';
    return o;
}""")
print(f"\n[1] 原 style = {orig!r}")
info = page.evaluate("""() => {
    const input = document.querySelector('.article-bar__title--input');
    if (!input) return null;
    const r = input.getBoundingClientRect();
    const st = window.getComputedStyle(input);
    const top = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
    return {display: st.display, disabled: input.disabled, readOnly: input.readOnly,
            rect: {x: r.x|0, y: r.y|0, w: r.width|0, h: r.height|0},
            topEl: top ? top.tagName + '.' + String(top.className).slice(0,40) : null,
            topIsInput: top === input};
}""")
print(f"[2] input 状态: {json.dumps(info, ensure_ascii=False)}")

# 原生点击（不吞异常）
TITLE = "Python 协程全景解析：从原理到生产实战"
inp = page.locator('.article-bar__title--input').first
try:
    inp.click(timeout=6000, force=False)
    print("[3] 原生 click 成功")
except Exception as e:
    print(f"[3] 原生 click 失败: {type(e).__name__}: {str(e)[:200]}")
    # 试试 force click
    try:
        inp.click(timeout=4000, force=True)
        print("[3b] force click 成功")
    except Exception as e2:
        print(f"[3b] force click 也失败: {type(e2).__name__}")

page.keyboard.press("Control+A")
page.keyboard.press("Delete")
page.keyboard.type(TITLE, delay=25)
time.sleep(1)

after = page.evaluate("""() => ({
    inputVal: document.querySelector('.article-bar__title--input')?.value,
    displayTxt: document.querySelector('.article-bar__title-display')?.innerText,
    focusTag: document.activeElement ? document.activeElement.tagName + '.' + String(document.activeElement.className).slice(0,40) : null
})""")
print(f"\n[4] 输入后: {json.dumps(after, ensure_ascii=False)}")
blen2 = page.evaluate("() => document.querySelector('pre.editor__inner[contenteditable=true]')?.innerText.length || 0")
print(f"[5] 正文长度 after = {blen2}  (被误伤: {blen2 != blen})")

# 焦点在标题框时输入是否被框架接受——再看草稿标题（draft 状态）
# CSDN 会把标题写进 draft auto-save；打开弹窗看弹窗里的 title 相关状态
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(8)
modal_title = page.evaluate("""() => {
    // 弹窗 header 的 H3 是"发布文章"固定文字；找 input 显示的标题
    return {
        inputVal: document.querySelector('.article-bar__title--input')?.value,
        displayTxt: document.querySelector('.article-bar__title-display')?.innerText,
    };
}""")
print(f"[6] 开弹窗后: {json.dumps(modal_title, ensure_ascii=False)}")

try:
    page.screenshot(path="data/csdn_title71.png")
except Exception:
    pass
br.close()
