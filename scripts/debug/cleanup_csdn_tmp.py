# -*- coding: utf-8 -*-
"""CSDN mp 后台 UI 删除 tmp 标题的测试文章。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

TARGETS = ["tmp89nwlmai", "tmpiqohcvaa", "tmpwsku4p9h"]

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(6)
print(f"URL: {page.url}")

for title in TARGETS:
    # 刷新列表页面（删一篇后 DOM 变化）
    if page.url.startswith("about:") or "manage/article" not in page.url:
        page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
                  timeout=60000, wait_until="domcontentloaded")
        time.sleep(5)
    try:
        # 找到包含该标题的行
        row = page.locator(f"tr:has-text('{title}'), [class*=item]:has-text('{title}')").first
        cnt = page.locator(f"text={title}").count()
        if cnt == 0:
            print(f"{title}: 列表中未找到（可能已删）")
            continue
        # 行内找"删除"按钮
        del_btn = row.locator("button:has-text('删除'), a:has-text('删除')").first
        del_btn.click(timeout=6000)
        time.sleep(2)
        # 确认弹窗：找 确定/确认/删除 按钮
        confirm = page.locator(
            ".el-message-box__btns button:has-text('确定'), "
            ".el-message-box__btns button:has-text('删除'), "
            "[class*=dialog] button:has-text('确定'), "
            "[class*=dialog] button:has-text('确认')").first
        confirm.click(timeout=6000)
        time.sleep(3)
        print(f"{title}: 已提交删除")
    except Exception as e:
        print(f"{title}: 删除失败 {type(e).__name__}: {str(e)[:150]}")

time.sleep(3)
# 验证
try:
    page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
              timeout=60000, wait_until="domcontentloaded")
    time.sleep(6)
    body = page.evaluate("() => document.body.innerText.slice(0, 4000)")
    remaining = [t for t in TARGETS if t in body]
    print(f"仍存在的 tmp 标题: {remaining or '无，全部删除成功'}")
except Exception as e:
    print(f"验证失败: {e}")
br.close()
