# -*- coding: utf-8 -*-
"""发布链路实测探针：逐平台模拟真实发布，检查每一步是否走到。
用法：python publish_probe.py [平台名]
不传则逐平台跑。每步结果清晰打印，不实际发出去（只到发布弹窗为止）。
"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core.service as sv
from core.adapters.base import get_adapter
from core.browser import BuiltinBrowser

TEST_ARTICLE = {
    "title": "测试文章：Python 协程入门",
    "content_md": "# Python 协程入门\n\n协程是比线程更轻量的并发原语。\n\n```python\nimport asyncio\n\nasync def main():\n    print('hello coroutine')\n\nasyncio.run(main())\n```\n\n## 小结\n协程适合 IO 密集型场景。",
    "summary": "协程入门",
    "tags": "Python,异步",
}


def probe_platform(platform):
    ad = get_adapter(platform)
    print(f"\n{'='*60}\nPROBE: {platform} ({ad.name})\n{'='*60}")

    br = BuiltinBrowser(platform, "default", headless=True)
    page = br.start().new_page()

    # 1. 登录态
    try:
        page.goto(ad.home_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(2)
        ok = ad.check_auth(page)
        print(f"  [1] 登录态: {'OK' if ok else 'FAIL'}")
        if not ok:
            print(f"  => 跳过（未登录）")
            br.close()
            return
    except Exception as e:
        print(f"  [1] 登录态检查异常: {str(e)[:60]}")
        br.close()
        return

    # 2. 进编辑器
    try:
        page.goto(ad.new_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(5)
        print(f"  [2] 编辑器页: {page.url[:60]}")
    except Exception as e:
        print(f"  [2] 编辑器页失败: {str(e)[:60]}")
        br.close()
        return

    # 3. 找标题输入框并填入
    title_filled = False
    for sel in [
        'input[placeholder*="标题"]', 'textarea[placeholder*="标题"]',
        'input.article-bar__title', '.article-bar__title input',
        'input[placeholder*="输入文章标题"]', 'textarea[placeholder*="请输入标题"]',
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                page.keyboard.type(TEST_ARTICLE["title"])
                title_filled = True
                print(f"  [3] 标题填入 OK (selector: {sel})")
                break
        except Exception:
            continue
    if not title_filled:
        print("  [3] 标题填入: 没找到可见标题框")

    # 4. 填正文
    content_filled = False
    content_method = ""
    # CSDN 有专用方法
    if hasattr(ad, "_set_cs_editor"):
        try:
            m = ad._set_cs_editor(page, TEST_ARTICLE["content_md"])
            content_filled = True
            content_method = f"csdn:{m}"
        except Exception as e:
            content_method = f"csdn:ERR({str(e)[:40]})"
    elif hasattr(ad, "_inject_editor"):
        try:
            ad._inject_editor(page, TEST_ARTICLE["content_md"])
            content_filled = True
            content_method = "inject_editor (keyboard)"
        except Exception as e:
            content_method = f"inject:ERR({str(e)[:40]})"
    else:
        # 其它平台用 set_editor_content（CodeMirror / DraftJS 等）
        try:
            m = ad.set_editor_content(page, TEST_ARTICLE["content_md"])
            content_filled = True
            content_method = m
        except Exception as e:
            content_method = f"ERR({str(e)[:40]})"
    print(f"  [4] 正文填入: {'OK' if content_filled else 'FAIL'} ({content_method})")

    # 验证正文是否真填上
    try:
        # 知乎用 .public-DraftEditor-content（Playwright 不识别其 contenteditable）
        draft_ed = page.query_selector('.public-DraftEditor-content')
        cm = page.query_selector('.CodeMirror')
        ce = page.query_selector('[contenteditable=true]')
        if draft_ed:
            body_len = len(page.evaluate("el => el.innerText || ''", draft_ed))
        elif cm and hasattr(cm, "CodeMirror"):
            body_len = len(cm.evaluate("el => el.CodeMirror ? el.CodeMirror.getValue() : ''"))
        elif ce:
            body_len = len(page.evaluate("el => el.innerText || ''", ce))
        else:
            body_len = 0
        print(f"      正文长度: {body_len} 字符")
    except Exception as e:
        print(f"      正文验证异常: {str(e)[:40]}")

    # 5. 点发布，看弹窗字段
    publish_clicked = False
    for sel in ['button.btn-publish', 'button:has-text("发布")', '.btn-publish',
                'button.xitu-btn', '.css-d0uhtl']:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                publish_clicked = True
                print(f"  [5] 点发布 OK (selector: {sel})")
                break
        except Exception:
            continue
    if publish_clicked:
        time.sleep(3)
        # 检查弹窗里的字段
        dialog = page.query_selector('[class*=modal], [class*=dialog], [class*=popover], .el-dialog')
        if dialog:
            # 标签输入
            tag_input = page.query_selector('input[placeholder*=标签], input[class*=tag], [class*=tag] input')
            print(f"      弹窗: 有 | 标签输入: {'有' if tag_input else '无'}")
            # 分类
            cat_input = page.query_selector('[class*=category] input, select, [class*=分类] select')
            print(f"      弹窗: 有 | 分类选择: {'有' if cat_input else '无'}")
            # 摘要
            abstract = page.query_selector('textarea[placeholder*=摘要], textarea[placeholder*=描述]')
            print(f"      弹窗: 有 | 摘要输入: {'有' if abstract else '无'}")
        else:
            print(f"  [5] 点发布后: 无弹窗/直接发布/或卡在某处 (URL: {page.url[:60]})")
    else:
        print(f"  [5] 没找到可见发布按钮")
        # 看有没有隐藏发布按钮
        hidden_pub = page.query_selector_all('button:has-text("发布")')
        print(f"      隐藏发布按钮: {len(hidden_pub)} 个")

    # 截图
    try:
        page.screenshot(path=f"data/probe_{platform}.png")
        print(f"  [6] 截图: data/probe_{platform}.png")
    except Exception:
        pass

    br.close()


if __name__ == "__main__":
    platforms = sys.argv[1:] if len(sys.argv) > 1 else ["csdn", "zhihu", "juejin"]
    for p in platforms:
        try:
            probe_platform(p)
        except Exception as e:
            print(f"\nPROBE {p} 异常: {e}")
        time.sleep(2)
