# -*- coding: utf-8 -*-
"""CSDN 删除终搏：抓全量 API + 弹窗按钮双保险点击。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGETS = ["tmpwsku4p9h"]

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()

api_hits = []
def on_resp(resp):
    u = resp.url
    # 抓 mp 后台业务 API（排除静态资源与统计）
    if ("mp.csdn.net" in u or "blog.csdn.net" in u) and \
       not any(k in u for k in (".js", ".css", ".png", ".jpg", ".woff", "eva2", "retcode")):
        if resp.request.method in ("POST", "PUT", "DELETE") or "act" in u:
            try:
                body = (resp.request.post_data or "")[:150]
            except Exception:
                body = ""
            try:
                txt = resp.text()[:200]
            except Exception:
                txt = "(no)"
            api_hits.append({"m": resp.request.method, "u": u[:130], "s": resp.status,
                             "body": body, "resp": txt})
page.on("response", on_resp)

page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(8)

title = TARGETS[0]
row = page.locator(f".list-item-mp-right:has-text('{title}')").first
print(f"row count: {row.count()}")

row.hover(timeout=5000)
time.sleep(0.8)
row.locator(".el-dropdown-link").first.hover(timeout=5000)
time.sleep(2.0)

# 几何找删除项
vis = page.evaluate("""() => {
    for (const e of document.querySelectorAll('li')) {
        if ((e.innerText||'').trim() !== '删除') continue;
        const r = e.getBoundingClientRect();
        if (r.width > 20 && r.height > 10 && r.x > 0 && r.y > 0) {
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
    }
    return null;
}""")
print(f"删除菜单项: {vis}")
if not vis:
    br.close(); sys.exit(1)

page.mouse.click(vis["x"], vis["y"])
time.sleep(3)

# 弹窗按钮详查
btns = page.evaluate("""() => {
    const out = [];
    for (const b of document.querySelectorAll('button')) {
        const t = (b.innerText||'').trim();
        if (!t || b.offsetParent === null) continue;
        const r = b.getBoundingClientRect();
        out.push({t, cls: String(b.className||'').slice(0,40),
                  x: (r.x + r.width/2)|0, y: (r.y + r.height/2)|0});
    }
    return out;
}""")
print("可见按钮:", json.dumps(btns, ensure_ascii=False))

# 点确定（先 mouse，后 JS 双保险）
cand = [b for b in btns if b["t"] in ("确定", "确认删除", "确认")]
if cand:
    tgt = cand[-1]
    api_hits.clear()
    print(f"\nmouse click {tgt['t']!r} @({tgt['x']},{tgt['y']})")
    page.mouse.click(tgt["x"], tgt["y"])
    time.sleep(3)
    n1 = len(api_hits)
    print(f"mouse 点击后 API: {n1} 个")
    if n1 == 0:
        print("JS click 兜底…")
        page.evaluate("""() => {
            for (const b of document.querySelectorAll('button')) {
                const t = (b.innerText||'').trim();
                if (t === '确定' && b.offsetParent !== null) { b.click(); return; }
            }
        }""")
        time.sleep(3)

print(f"\n=== 捕获 {len(api_hits)} 个业务请求 ===")
for r in api_hits:
    print(f"  [{r['s']}] {r['m']} {r['u']}")
    if r["body"]: print(f"      req: {r['body']}")
    print(f"      resp: {r['resp'][:150]}")

time.sleep(2)
resp = page.goto("https://blog.csdn.net/weixin_56622231/article/details/166252870",
                 timeout=60000, wait_until="domcontentloaded")
print(f"\n验证 166252870: HTTP {resp.status}")
br.close()
