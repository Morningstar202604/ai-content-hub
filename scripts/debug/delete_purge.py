# -*- coding: utf-8 -*-
"""CSDN 彻底删除：行按钮直接点"彻底删除"（文章已在回收/草稿态）。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGETS = ["tmpwsku4p9h", "tmpiqohcvaa", "tmp89nwlmai"]
AIDS = ["166252870", "166252818", "166252770"]

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()

page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(8)

for title in TARGETS:
    try:
        # 重新加载行（每删一篇 DOM 变化）
        row_c = page.evaluate("""(t) => {
            const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
            const row = rows.find(r => r.innerText.includes(t));
            if (!row) return null;
            const r = row.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }""", title)
        if not row_c:
            print(f"{title}: 行不在列表（可能已删）")
            continue
        page.mouse.move(row_c["x"], row_c["y"])
        time.sleep(1.5)

        # 找可见的"彻底删除"按钮
        btn = page.evaluate("""(t) => {
            const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
            const row = rows.find(r => r.innerText.includes(t));
            if (!row) return null;
            for (const e of row.querySelectorAll('a, button, span, div')) {
                if ((e.innerText||'').trim() !== '彻底删除') continue;
                const r = e.getBoundingClientRect();
                if (r.width > 10 && r.height > 5 && r.x > 0 && r.y > 0) {
                    return {x: r.x + r.width/2, y: r.y + r.height/2};
                }
            }
            return null;
        }""", title)
        if not btn:
            print(f"{title}: 彻底删除按钮未出现")
            continue
        page.mouse.click(btn["x"], btn["y"])
        time.sleep(3)

        # 确认弹窗
        conf = page.evaluate("""() => {
            for (const b of document.querySelectorAll('button')) {
                const t = (b.innerText||'').trim();
                if (!['确定','确认删除','确认','彻底删除'].includes(t)) continue;
                const r = b.getBoundingClientRect();
                if (r.width > 10 && r.x > 0 && r.y > 0) {
                    return {x: r.x + r.width/2, y: r.y + r.height/2, t};
                }
            }
            return null;
        }""")
        if not conf:
            print(f"{title}: 确认弹窗未出现")
            page.keyboard.press("Escape")
            time.sleep(1.5)
            continue
        page.mouse.click(conf["x"], conf["y"])
        print(f"{title}: 已点 {conf['t']!r}")
        time.sleep(3.5)
        page.reload(wait_until="domcontentloaded")
        time.sleep(7)
    except Exception as e:
        print(f"{title}: 异常 {type(e).__name__}: {str(e)[:120]}")
        page.reload(wait_until="domcontentloaded")
        time.sleep(7)

# 终验：列表 + 文章 URL
body = page.evaluate("() => document.body.innerText")
remaining = [t for t in TARGETS if t in body]
print(f"\n列表仍存在: {remaining or '无，全部删除成功'}")
br.close()

br2 = BuiltinBrowser("csdn", "default", headless=True)
p2 = br2.start().new_page()
for aid in AIDS:
    resp = p2.goto(f"https://blog.csdn.net/weixin_56622231/article/details/{aid}",
                   timeout=60000, wait_until="domcontentloaded")
    print(f"文章 {aid}: HTTP {resp.status if resp else '?'}")
br2.close()
