# -*- coding: utf-8 -*-
"""CSDN 删除 tmp 文章终版：hover → hover dropdown → 坐标点删除 → 确认。"""
import sys, time

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGETS = ["tmpwsku4p9h", "tmpiqohcvaa", "tmp89nwlmai"]

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(7)

def delete_one(title):
    row = page.locator(f".list-item-mp-right:has-text('{title}')").first
    if row.count() == 0:
        print(f"{title}: 行未找到")
        return False
    row.hover(timeout=5000)
    time.sleep(0.8)
    row.locator(".el-dropdown-link").first.hover(timeout=5000)
    time.sleep(1.8)
    # 找可见的删除菜单项
    vis = page.evaluate("""() => {
        for (const e of document.querySelectorAll('li')) {
            if ((e.innerText||'').trim() === '删除' && e.offsetParent !== null) {
                const r = e.getBoundingClientRect();
                if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
            }
        }
        return null;
    }""")
    if not vis:
        print(f"{title}: 删除菜单未出现")
        return False
    page.mouse.click(vis["x"], vis["y"])
    time.sleep(2)
    # 确认弹窗：找可见的 确定删除/确定/删除 按钮
    btn = page.evaluate("""() => {
        for (const b of document.querySelectorAll('button')) {
            const t = (b.innerText||'').trim();
            if (b.offsetParent !== null && (t === '确定' || t === '确认删除' || t === '删除' || t === '确认')) {
                const r = b.getBoundingClientRect();
                if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2, t};
            }
        }
        return null;
    }""")
    if not btn:
        print(f"{title}: 确认弹窗未出现")
        page.keyboard.press("Escape")
        return False
    page.mouse.click(btn["x"], btn["y"])
    print(f"{title}: 点了确认按钮 {btn['t']!r}")
    time.sleep(3)
    return True

for t in TARGETS:
    try:
        ok = delete_one(t)
        if ok:
            # 回列表页刷新
            page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
                      timeout=60000, wait_until="domcontentloaded")
            time.sleep(6)
    except Exception as e:
        print(f"{t}: 异常 {type(e).__name__}: {str(e)[:150]}")
        try:
            page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
                      timeout=60000, wait_until="domcontentloaded")
            time.sleep(6)
        except Exception:
            pass

# 终验
try:
    page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
              timeout=60000, wait_until="domcontentloaded")
    time.sleep(6)
    body = page.evaluate("() => document.body.innerText")
    remaining = [t for t in TARGETS if t in body]
    print(f"\n仍存在的 tmp 标题: {remaining or '无，全部删除成功'}")
except Exception as e:
    print(f"终验失败: {e}")
br.close()
