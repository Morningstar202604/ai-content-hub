# -*- coding: utf-8 -*-
"""CSDN 删除文章：全程抓网络，确认弹窗结构详查。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TITLE = "tmpwsku4p9h"

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()

reqs = []
def on_req(req):
    u = req.url
    if any(k in u.lower() for k in ("delete", "remove", "recycle", "del")):
        try:
            reqs.append({"m": req.method, "u": u[:150], "body": (req.post_data or "")[:200]})
        except Exception:
            pass
page.on("request", on_req)

def open_dropdown(page, title):
    """hover 行 → hover 更多按钮 → 返回可见'删除'菜单项坐标。带重试。"""
    for attempt in range(3):
        try:
            row = page.locator(f".list-item-mp-right:has-text('{title}')").first
            if row.count() == 0:
                return None, "行未找到"
            row.hover(timeout=5000)
            time.sleep(1.0)
            row.locator(".el-dropdown-link").first.hover(timeout=5000)
            time.sleep(2.0)
            vis = page.evaluate("""() => {
                for (const e of document.querySelectorAll('li')) {
                    if ((e.innerText||'').trim() === '删除' && e.offsetParent !== null) {
                        const r = e.getBoundingClientRect();
                        if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
                return null;
            }""")
            if vis:
                return vis, None
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:100]}"
        time.sleep(2)
    return None, "下拉未出现"

page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(7)

vis, err = open_dropdown(page, TITLE)
print(f"删除菜单项: {vis} {err or ''}")
if not vis:
    br.close(); sys.exit(1)

page.mouse.click(vis["x"], vis["y"])
time.sleep(3)

# 详查弹窗
d = page.evaluate("""() => {
    // 所有可见的覆盖层/对话框
    const overlays = Array.from(document.querySelectorAll('div'))
      .filter(e => {
          const st = window.getComputedStyle(e);
          return st.position === 'fixed' && e.offsetWidth > 200 && e.offsetHeight > 80
                 && st.zIndex && parseInt(st.zIndex) > 100;
      })
      .map(e => ({cls: String(e.className||'').slice(0,60),
                  z: window.getComputedStyle(e).zIndex,
                  text: (e.innerText||'').slice(0,200).replace(/\\n/g,'|')}));
    // 弹窗内/页面上的全部可见按钮（带坐标）
    const btns = Array.from(document.querySelectorAll('button'))
      .filter(b => b.offsetParent !== null)
      .map(b => { const r = b.getBoundingClientRect();
          return {t: (b.innerText||'').trim(), cls: String(b.className||'').slice(0,50),
                  x: (r.x + r.width/2)|0, y: (r.y + r.height/2)|0}; })
      .filter(b => b.t);
    return {overlays: overlays.slice(0, 6), btns};
}""")
print("\n=== 覆盖层 ===")
for o in d["overlays"]:
    print(f"  z={o['z']} {o['cls']!r} text={o['text'][:100]!r}")
print("\n=== 可见按钮 ===")
for b in d["btns"]:
    print(f"  {b['t']!r:20s} cls={b['cls']!r:45s} @({b['x']},{b['y']})")

# 点确认（找对话框语境里的确定/删除按钮：坐标在弹窗附近或 class 含 primary）
cand = [b for b in d["btns"] if b["t"] in ("确定", "确认删除", "删除", "确认")]
print(f"\n候选确认按钮: {[(c['t'], c['x'], c['y'], c['cls']) for c in cand]}")
if cand:
    # 优先 class 含 danger/primary 的
    cand.sort(key=lambda b: 0 if ("danger" in b["cls"] or "primary" in b["cls"]) else 1)
    tgt = cand[0]
    print(f"点击: {tgt['t']!r} @({tgt['x']},{tgt['y']})")
    page.mouse.click(tgt["x"], tgt["y"])
    time.sleep(4)
    print(f"\n抓到 {len(reqs)} 个 delete 相关请求:")
    for r in reqs:
        print(f"  {r['m']} {r['u']}")
        if r["body"]: print(f"      {r['body']}")

# 验证
resp = page.goto(f"https://blog.csdn.net/weixin_56622231/article/details/166252870",
                 timeout=60000, wait_until="domcontentloaded")
print(f"\n文章 166252870 状态: {resp.status}")
br.close()
