# -*- coding: utf-8 -*-
"""CSDN mp 后台删除 tmp 测试文章：hover → el-dropdown 更多菜单 → 删除 → 确认。"""
import sys, time

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGETS = ["tmpwsku4p9h", "tmpiqohcvaa", "tmp89nwlmai"]

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(7)

for title in TARGETS:
    try:
        row = page.locator(f".list-item-mp-right:has-text('{title}')").first
        if row.count() == 0:
            print(f"{title}: 行未找到（可能已删）")
            continue
        row.hover(timeout=5000)
        time.sleep(1)
        row.locator(".el-dropdown-link").first.click(timeout=5000)
        time.sleep(2)
        # 全局找下拉菜单里的"删除"
        menu_item = page.locator(
            ".el-dropdown-menu li:has-text('删除'), "
            "[class*=dropdown-menu] li:has-text('删除'), "
            "[class*=dropdown-menu] :text('删除')").first
        menu_item.click(timeout=5000)
        time.sleep(2)
        # 确认弹窗（可能是 el-message-box 或自定义 dialog）
        confirm = page.locator(
            ".el-message-box__btns button:has-text('确定'), "
            ".el-message-box__btns button:has-text('删除'), "
            "button:has-text('确认删除'), "
            "[class*=dialog] button:has-text('确定')").first
        confirm.click(timeout=5000)
        time.sleep(3)
        print(f"{title}: 已提交删除")
        # 回列表页刷新
        page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
                  timeout=60000, wait_until="domcontentloaded")
        time.sleep(6)
    except Exception as e:
        print(f"{title}: 删除失败 {type(e).__name__}: {str(e)[:180]}")
        try:
            page.keyboard.press("Escape")
            time.sleep(1)
            page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
                      timeout=60000, wait_until="domcontentloaded")
            time.sleep(6)
        except Exception:
            pass

# 终验
try:
    body = page.evaluate("() => document.body.innerText")
    remaining = [t for t in TARGETS if t in body]
    print(f"\n仍存在的 tmp 标题: {remaining or '无，全部删除成功'}")
except Exception as e:
    print(f"终验失败: {e}")
br.close()
