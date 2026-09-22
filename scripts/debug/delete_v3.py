# -*- coding: utf-8 -*-
"""CSDN 删除最终版：JS 定位坐标 + 原始 mouse 事件 + 重试循环。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGETS = ["tmpwsku4p9h", "tmpiqohcvaa", "tmp89nwlmai"]

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()

api_hits = []
def on_resp(resp):
    u = resp.url
    if ("mp.csdn.net" in u or "blog.csdn.net" in u) and \
       not any(k in u for k in (".js", ".css", ".png", ".jpg", ".woff", "eva2", "retcode")):
        if resp.request.method in ("POST", "PUT", "DELETE"):
            try:
                txt = resp.text()[:180]
            except Exception:
                txt = "(no)"
            api_hits.append({"m": resp.request.method, "u": u[:120], "s": resp.status, "resp": txt})
page.on("response", on_resp)

def js_rect(page, js):
    """执行 JS 返回坐标；元素未渲染返回 None。"""
    return page.evaluate(js)

ROW_JS = """(title) => {
    const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
    const row = rows.find(r => r.innerText.includes(title));
    if (!row) return null;
    const r = row.getBoundingClientRect();
    if (r.width <= 0) return null;
    return {x: r.x + r.width/2, y: r.y + r.height/2};
}"""

DD_JS = """(title) => {
    const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
    const row = rows.find(r => r.innerText.includes(title));
    if (!row) return null;
    const dd = row.querySelector('.el-dropdown-link');
    if (!dd) return null;
    const r = dd.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return null;
    return {x: r.x + r.width/2, y: r.y + r.height/2};
}"""

DEL_LI_JS = """() => {
    for (const e of document.querySelectorAll('li')) {
        if ((e.innerText||'').trim() !== '删除') continue;
        const r = e.getBoundingClientRect();
        if (r.width > 20 && r.height > 10 && r.x > 0 && r.y > 0) {
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
    }
    return null;
}"""

def try_delete(page, title):
    for attempt in range(5):
        # 第一步：鼠标先移到行中心（行永远可见），触发按钮浮现
        row_c = page.evaluate(ROW_JS, title)
        if not row_c:
            time.sleep(2)
            continue
        page.mouse.move(row_c["x"] - 80, row_c["y"] - 15)
        time.sleep(0.4)
        page.mouse.move(row_c["x"], row_c["y"])
        time.sleep(1.2)
        # 第二步：按钮已浮现，再定位 dropdown 并移过去
        dd = page.evaluate(DD_JS, title)
        if not dd:
            time.sleep(1.5)
            continue
        page.mouse.move(dd["x"], dd["y"])
        time.sleep(2.2)
        vis = page.evaluate(DEL_LI_JS)
        if not vis:
            # 也试一次原生 click 触发 dropdown
            page.mouse.click(dd["x"], dd["y"])
            time.sleep(2.2)
            vis = page.evaluate(DEL_LI_JS)
        if not vis:
            continue
        page.mouse.click(vis["x"], vis["y"])
        time.sleep(3)
        # 找确认按钮（几何）
        btn = page.evaluate("""() => {
            for (const b of document.querySelectorAll('button')) {
                const t = (b.innerText||'').trim();
                if (!['确定','确认删除','确认'].includes(t)) continue;
                const r = b.getBoundingClientRect();
                if (r.width > 10 && r.x > 0 && r.y > 0) {
                    return {x: r.x + r.width/2, y: r.y + r.height/2};
                }
            }
            return null;
        }""")
        if not btn:
            page.keyboard.press("Escape")
            time.sleep(1.5)
            continue
        page.mouse.click(btn["x"], btn["y"])
        time.sleep(3.5)
        return True
    return False

page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(8)

for t in TARGETS:
    ok = try_delete(page, t)
    print(f"{t}: {'已执行删除流程' if ok else '菜单/确认未出现'}")
    api_hits.clear() if not ok else None
    page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
              timeout=60000, wait_until="domcontentloaded")
    time.sleep(7)

print(f"\n=== 捕获 {len(api_hits)} 个 POST ===")
for r in api_hits:
    print(f"  [{r['s']}] {r['m']} {r['u']}  {r['resp'][:100]}")

body = page.evaluate("() => document.body.innerText")
remaining = [t for t in TARGETS if t in body]
print(f"\n列表仍存在: {remaining or '无，全部删除成功'}")
br.close()
