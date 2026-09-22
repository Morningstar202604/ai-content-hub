# -*- coding: utf-8 -*-
"""删除重复文章 166254225（同名文章用 href 区分，两段式删除）。"""
import sys, time

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGET_ID = "166254225"

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(7)

def row_by_href(page, aid):
    """按行内链接 href 找文章行中心（同名文章的唯一区分方式）。"""
    return page.evaluate("""(aid) => {
        const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
        const row = rows.find(r => r.querySelector(`a[href*='${aid}']`));
        if (!row) return null;
        const r = row.getBoundingClientRect();
        return {x: r.x + r.width/2, y: r.y + r.height/2};
    }""", aid)

def dd_of_row(page, aid):
    return page.evaluate("""(aid) => {
        const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
        const row = rows.find(r => r.querySelector(`a[href*='${aid}']`));
        const dd = row && row.querySelector('.el-dropdown-link');
        if (!dd) return null;
        const r = dd.getBoundingClientRect();
        if (r.width <= 0) return null;
        return {x: r.x + r.width/2, y: r.y + r.height/2};
    }""", aid)

def visible_del_li(page):
    return page.evaluate("""() => {
        for (const e of document.querySelectorAll('li')) {
            if ((e.innerText||'').trim() !== '删除') continue;
            const r = e.getBoundingClientRect();
            if (r.width > 20 && r.x > 0 && r.y > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
        return null;
    }""")

def visible_btn(page, texts):
    return page.evaluate("""(texts) => {
        for (const b of document.querySelectorAll('button')) {
            if (!texts.includes((b.innerText||'').trim())) continue;
            const r = b.getBoundingClientRect();
            if (r.width > 10 && r.x > 0 && r.y > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
        return null;
    }""", texts)

# ---- 第一段：删除（进回收态）----
rc = row_by_href(page, TARGET_ID)
print(f"行中心: {rc}")
if rc:
    page.mouse.move(rc["x"], rc["y"])
    time.sleep(1.5)
    dd = dd_of_row(page, TARGET_ID)
    print(f"dropdown: {dd}")
    if dd:
        page.mouse.move(dd["x"], dd["y"])
        time.sleep(2.2)
        vis = visible_del_li(page)
        print(f"删除菜单项: {vis}")
        if vis:
            page.mouse.click(vis["x"], vis["y"])
            time.sleep(3)
            conf = visible_btn(page, ["确定", "确认删除", "确认"])
            print(f"确认按钮: {conf}")
            if conf:
                page.mouse.click(conf["x"], conf["y"])
                print("第一段完成（进回收态）")
                time.sleep(4)
                page.reload(wait_until="domcontentloaded")
                time.sleep(7)

                # ---- 第二段：彻底删除 ----
                btn = page.evaluate("""(aid) => {
                    const rows = Array.from(document.querySelectorAll('.list-item-mp-right'));
                    const row = rows.find(r => r.querySelector(`a[href*='${aid}']`));
                    if (!row) return null;
                    for (const e of row.querySelectorAll('a, button, span, div')) {
                        if ((e.innerText||'').trim() !== '彻底删除') continue;
                        const r = e.getBoundingClientRect();
                        if (r.width > 10 && r.x > 0 && r.y > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                    return null;
                }""", TARGET_ID)
                print(f"彻底删除按钮: {btn}")
                if btn:
                    page.mouse.move(btn["x"], btn["y"])
                    time.sleep(0.5)
                    page.mouse.click(btn["x"], btn["y"])
                    time.sleep(3)
                    conf2 = visible_btn(page, ["确定", "确认删除", "确认", "彻底删除"])
                    print(f"二次确认: {conf2}")
                    if conf2:
                        page.mouse.click(conf2["x"], conf2["y"])
                        print("第二段完成")
                        time.sleep(4)

resp = page.goto(f"https://blog.csdn.net/weixin_56622231/article/details/{TARGET_ID}",
                 timeout=60000, wait_until="domcontentloaded")
print(f"\n终验 {TARGET_ID}: HTTP {resp.status if resp else '?'} (404=删除成功)")
br.close()
