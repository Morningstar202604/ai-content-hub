# -*- coding: utf-8 -*-
"""抓删除 API：hover → 菜单删除 → 确认，全程抓请求。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()

reqs = []
def on_req(req):
    u = req.url
    if any(k in u for k in ("delete", "remove", "recycle")):
        try:
            reqs.append({"m": req.method, "u": u, "body": (req.post_data or "")[:200]})
        except Exception:
            pass
page.on("request", on_req)

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
print(f"删除菜单项: {vis}")
page.mouse.click(vis["x"], vis["y"])
time.sleep(2.5)

# dump 弹窗
d = page.evaluate("""() => {
    const btns = Array.from(document.querySelectorAll('button'))
        .filter(b => b.offsetParent !== null)
        .map(b => ({t: (b.innerText||'').trim(), cls: String(b.className||'').slice(0,50),
                    x: b.getBoundingClientRect().x|0, y: b.getBoundingClientRect().y|0}))
        .filter(b => b.t);
    return btns;
}""")
print("可见按钮:", json.dumps(d, ensure_ascii=False))
br.close()
