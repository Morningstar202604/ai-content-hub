# -*- coding: utf-8 -*-
"""CSDN mp 后台删除 tmp 测试文章：hover 行 → 更多菜单 → 删除 → 确认。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGETS = ["tmpwsku4p9h", "tmpiqohcvaa", "tmp89nwlmai"]

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(7)

# 先 dump 第一个 tmp 行内所有元素（含无文本的图标按钮）
probe = page.evaluate("""() => {
    const all = Array.from(document.querySelectorAll('*'));
    const inner = all.find(e => e.children.length === 0 && (e.textContent||'').includes('tmpwsku4p9h'));
    if (!inner) return {found: false};
    let row = inner;
    for (let i = 0; i < 8 && row; i++) {
        if (String(row.className||'').includes('list-item-mp-right')) break;
        row = row.parentElement;
    }
    const els = Array.from(row.querySelectorAll('*')).map(e => ({
        tag: e.tagName, cls: String(e.className||'').slice(0, 50),
        text: (e.innerText||'').trim().slice(0, 12),
        title: e.title || e.getAttribute('aria-label') || ''
    })).filter(e => e.tag === 'BUTTON' || e.tag === 'A' || e.tag === 'SPAN' || e.tag === 'svg' || e.cls);
    return {found: true, rowCls: String(row.className), els: els.slice(0, 40)};
}""")
print(json.dumps(probe, ensure_ascii=False, indent=1)[:2500])

# hover 行看隐藏按钮
try:
    row = page.locator(".list-item-mp-right:has-text('tmpwsku4p9h')").first
    row.hover(timeout=5000)
    time.sleep(1.5)
    hover_btns = row.evaluate("""(r) => Array.from(r.querySelectorAll('a, button, span, div[class*=oper], svg'))
        .map(e => ({tag: e.tagName, cls: String(e.className&&e.className.baseVal!==undefined ? e.className.baseVal : e.className||'').slice(0,40),
                    text: (e.innerText||'').trim().slice(0,10),
                    vis: e.offsetParent !== null}))
        .filter(e => e.vis)""")
    print("\n=== hover 后可见元素 ===")
    for b in hover_btns[-15:]:
        print(f"  <{b['tag']}> cls={b['cls']!r} text={b['text']!r}")
except Exception as e:
    print(f"hover 失败: {e}")
br.close()
