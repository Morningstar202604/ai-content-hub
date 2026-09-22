# -*- coding: utf-8 -*-
"""CSDN 删除 tmp 文章（终版 2）：几何判断菜单可见性 + 全程抓 API。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGETS = ["tmpwsku4p9h", "tmpiqohcvaa", "tmp89nwlmai"]

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()

api_hits = []
def on_resp(resp):
    u = resp.url
    if any(k in u.lower() for k in ("delete", "remove", "recycle")):
        try:
            api_hits.append({"m": resp.request.method, "u": u[:150],
                             "status": resp.status,
                             "body": (resp.request.post_data or "")[:150],
                             "resp": resp.text()[:150]})
        except Exception:
            api_hits.append({"m": resp.request.method, "u": u[:150], "status": resp.status})
page.on("response", on_resp)

def find_visible_del_li(page):
    """几何判断：text==删除 的 li 且 bounding box 合理（不依赖 offsetParent）。"""
    return page.evaluate("""() => {
        for (const e of document.querySelectorAll('li')) {
            if ((e.innerText||'').trim() !== '删除') continue;
            const r = e.getBoundingClientRect();
            if (r.width > 20 && r.height > 10 && r.x > 0 && r.y > 0 && r.y < innerHeight) {
                return {x: r.x + r.width/2, y: r.y + r.height/2};
            }
        }
        return null;
    }""")

def open_menu_and_get_del(page, title):
    """hover 行 → hover 更多 → 返回可见删除项坐标。带重试。"""
    for attempt in range(4):
        try:
            row = page.locator(f".list-item-mp-right:has-text('{title}')").first
            if row.count() == 0:
                return None
            box = row.bounding_box()
            if not box:
                return None
            # 人类式分步移到行中心
            cx, cy = box["x"] + box["width"]/2, box["y"] + box["height"]/2
            page.mouse.move(cx - 60, cy - 20)
            time.sleep(0.3)
            page.mouse.move(cx, cy)
            time.sleep(1.2)
            # 找 el-dropdown-link 的位置（hover 后应可见）
            dd = row.locator(".el-dropdown-link").first
            dbb = dd.bounding_box()
            if dbb:
                page.mouse.move(dbb["x"] + dbb["width"]/2, dbb["y"] + dbb["height"]/2)
                time.sleep(2.2)
                vis = find_visible_del_li(page)
                if vis:
                    return vis
            time.sleep(1.5)
        except Exception:
            time.sleep(2)
    return None

def click_visible_button(page, texts):
    """几何方式点可见按钮。"""
    return page.evaluate("""(texts) => {
        for (const b of document.querySelectorAll('button')) {
            const t = (b.innerText||'').trim();
            if (!texts.includes(t)) continue;
            const r = b.getBoundingClientRect();
            if (r.width > 10 && r.height > 10 && r.x > 0 && r.y > 0) {
                return {x: r.x + r.width/2, y: r.y + r.height/2, t};
            }
        }
        return null;
    }""", texts)

page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(8)

for title in TARGETS:
    vis = open_menu_and_get_del(page, title)
    if not vis:
        print(f"{title}: 删除菜单未出现")
        page.reload(wait_until="domcontentloaded")
        time.sleep(7)
        continue
    page.mouse.click(vis["x"], vis["y"])
    time.sleep(3)
    btn = click_visible_button(page, ["确定", "确认删除", "确认", "删除"])
    if not btn:
        print(f"{title}: 确认按钮未出现")
        page.keyboard.press("Escape")
        page.reload(wait_until="domcontentloaded")
        time.sleep(7)
        continue
    print(f"{title}: 点确认 {btn['t']!r} @({btn['x']},{btn['y']})")
    page.mouse.click(btn["x"], btn["y"])
    time.sleep(4)
    page.reload(wait_until="domcontentloaded")
    time.sleep(7)

print(f"\n=== 抓到 {len(api_hits)} 个删除相关请求 ===")
for r in api_hits:
    print(f"  [{r['status']}] {r['m']} {r['u']}")
    if r.get("body"): print(f"      req: {r['body']}")
    if r.get("resp"): print(f"      resp: {r['resp']}")

# 终验
body = page.evaluate("() => document.body.innerText")
remaining = [t for t in TARGETS if t in body]
print(f"\n列表仍存在: {remaining or '无，全部删除成功'}")
br.close()
