# -*- coding: utf-8 -*-
"""细调删除：点删除后 dump 确认弹窗。"""
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
row.locator(".el-dropdown-link").first.hover(timeout=5000)
time.sleep(1.8)
vis = page.evaluate("""() => {
    for (const e of document.querySelectorAll('li')) {
        if ((e.innerText||'').trim() === '删除' && e.offsetParent !== null) {
            const r = e.getBoundingClientRect();
            if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
    }
    return null;
}""")
page.mouse.click(vis["x"], vis["y"])
time.sleep(2.5)

d = page.evaluate("""() => {
    // 找弹窗/对话框
    const dlg = Array.from(document.querySelectorAll('[class*=dialog], [class*=modal], [class*=Dialog]'))
        .filter(e => e.offsetParent !== null && e.offsetWidth > 100);
    const info = dlg.map(e => ({
        cls: String(e.className||'').slice(0, 70),
        text: (e.innerText||'').slice(0, 300).replace(/\\n/g, '|'),
        btns: Array.from(e.querySelectorAll('button')).map(b => ({
            t: (b.innerText||'').trim(), vis: b.offsetParent !== null,
            cls: String(b.className||'').slice(0, 40)}))
    }));
    // 页面级可见按钮
    const allBtns = Array.from(document.querySelectorAll('button'))
        .filter(b => b.offsetParent !== null)
        .map(b => (b.innerText||'').trim()).filter(t => t);
    return {dialogs: info.slice(0, 5), allBtns: allBtns.slice(0, 20)};
}""")
print(json.dumps(d, ensure_ascii=False, indent=1))
br.close()
