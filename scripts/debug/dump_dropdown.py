# -*- coding: utf-8 -*-
"""点 el-dropdown-link 后 dump 全局新出现的菜单。"""
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
time.sleep(1)
before = set(page.evaluate("() => document.body.innerHTML.slice(0, 100)")[:1] and [])
# 记录点击前 body 的子元素数量
n_before = page.evaluate("() => document.querySelectorAll('body *').length")
row.locator(".el-dropdown-link").first.click(timeout=5000)
time.sleep(2.5)
n_after = page.evaluate("() => document.querySelectorAll('body *').length")
print(f"body 元素数: {n_before} -> {n_after} (新增 {n_after-n_before})")

# dump 含 删除/菜单 字样的新可见元素
items = page.evaluate("""() => {
    const out = [];
    for (const e of document.querySelectorAll('li, [class*=menu], [class*=dropdown], [class*=popper], [class*=tooltip]')) {
        const t = (e.innerText||'').trim().replace(/\\n/g, '|');
        if (t && (t.includes('删除') || t.includes('取消') || t.includes('置顶') || String(e.className).includes('dropdown'))) {
            out.push({tag: e.tagName, cls: String(e.className||'').slice(0, 60), text: t.slice(0, 60),
                      vis: e.offsetParent !== null});
        }
    }
    return out.slice(0, 20);
}""")
print(json.dumps(items, ensure_ascii=False, indent=1))
br.close()
