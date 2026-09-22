# -*- coding: utf-8 -*-
"""hover el-dropdown-link 触发菜单（el-dropdown 默认 hover 触发）。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(7)

row = page.locator(".list-item-mp-right:has-text('tmpwsku4p9h')").first
row.hover(timeout=5000)
time.sleep(0.8)
dd = row.locator(".el-dropdown-link").first
dd.hover(timeout=5000)
time.sleep(2)
n = page.evaluate("() => document.querySelectorAll('body *').length")

items = page.evaluate("""() => {
    const out = [];
    for (const e of document.querySelectorAll('li, [class*=menu] li, [class*=popper] li')) {
        const t = (e.innerText||'').trim().replace(/\\n/g, '|');
        if (t && t.includes('删除')) {
            const r = e.getBoundingClientRect();
            out.push({tag: e.tagName, cls: String(e.className||'').slice(0, 60), text: t.slice(0, 40),
                      vis: e.offsetParent !== null, rect: {x: r.x|0, y: r.y|0, w: r.width|0}});
        }
    }
    return out.slice(0, 10);
}""")
print(f"body: {n}")
print(json.dumps(items, ensure_ascii=False, indent=1))

if items:
    # 用坐标真实点击
    it = items[0]
    page.mouse.click(it["rect"]["x"] + it["rect"]["w"] // 2, it["rect"]["y"] + 10)
    print("已点删除菜单项")
    time.sleep(2)
    # 确认弹窗
    conf = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
        return btns.map(b => (b.innerText||'').trim()).filter(t => t);
    }""")
    print(f"当前可见按钮: {conf}")
br.close()
