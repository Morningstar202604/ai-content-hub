# -*- coding: utf-8 -*-
"""诊断：hover 后菜单 DOM 到底什么状态。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(8)

title = "tmpwsku4p9h"

# 1. hover 行
r1 = page.evaluate("""(t) => {
    const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
    const row = rows.find(r => r.innerText.includes(t));
    if (!row) return 'no row';
    const r = row.getBoundingClientRect();
    return {x: r.x + r.width/2, y: r.y + r.height/2};
}""", title)
print(f"行中心: {r1}")
page.mouse.move(r1["x"], r1["y"])
time.sleep(1.5)

# 2. hover 后：dd 状态 + 行内文本
state = page.evaluate("""(t) => {
    const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
    const row = rows.find(r => r.innerText.includes(t));
    if (!row) return null;
    const dd = row.querySelector('.el-dropdown-link');
    const ddr = dd ? dd.getBoundingClientRect() : null;
    return {
        rowText: row.innerText.slice(0, 120).replace(/\\n/g, '|'),
        ddRect: ddr ? {x: ddr.x|0, y: ddr.y|0, w: ddr.width|0, h: ddr.height|0} : null,
        ddVisible: dd ? dd.offsetParent !== null : null
    };
}""", title)
print(f"hover 后: {json.dumps(state, ensure_ascii=False)}")

# 3. hover dd
if state and state["ddRect"]:
    page.mouse.move(state["ddRect"]["x"] + state["ddRect"]["w"]/2,
                    state["ddRect"]["y"] + state["ddRect"]["h"]/2)
    time.sleep(2.5)

# 4. 全 DOM 扫删除元素（不管可见性）
dels = page.evaluate("""() => {
    const out = [];
    for (const e of document.querySelectorAll('li, [class*=menu], [class*=popper]')) {
        const t = (e.innerText||'').trim();
        if (!t.includes('删除')) continue;
        const r = e.getBoundingClientRect();
        const st = window.getComputedStyle(e);
        out.push({tag: e.tagName, cls: String(e.className||'').slice(0,50),
                  text: t.slice(0,30).replace(/\\n/g,'|'),
                  rect: {x: r.x|0, y: r.y|0, w: r.width|0, h: r.height|0},
                  display: st.display, vis: st.visibility, op: st.opacity});
    }
    return out.slice(0, 15);
}""")
print(f"\n删除相关元素 ({len(dels)}):")
for d in dels:
    print(f"  <{d['tag']}> {d['cls']!r} {d['text']!r} rect={d['rect']} disp={d['display']} vis={d['vis']}")

# 5. dd 位置的 elementFromPoint（看是不是被别的东西挡住）
if state and state["ddRect"]:
    cx = state["ddRect"]["x"] + state["ddRect"]["w"]/2
    cy = state["ddRect"]["y"] + state["ddRect"]["h"]/2
    top = page.evaluate(f"""([x, y]) => {{
        const e = document.elementFromPoint(x, y);
        return e ? e.tagName + '.' + String(e.className||'').slice(0,50) : 'nothing';
    }}""", [cx, cy])
    print(f"\ndd 中心 elementFromPoint: {top}")
br.close()
