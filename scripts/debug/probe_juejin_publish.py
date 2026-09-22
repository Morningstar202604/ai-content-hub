# -*- coding: utf-8 -*-
"""逆向掘金 publish 端点。

策略：
  1. 走 UI 发布面板：填入 tag 搜索框 → 选第一个候选 → 点"确定并发布"
  2. 同时用 page.on("request") 监听所有 XHR/fetch 到 content_api/v1/ 的请求
  3. 找出真正的 publish 端点 + 请求体

用法：python probe_juejin_publish.py
"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
import core.adapters.juejin  # 注册 JuejinAdapter
from core.adapters.base import get_adapter, PlatformError
from core.adapters.juejin import JuejinAdapter

CONTENT_MD = Path("data/test_article.md").read_text(encoding="utf-8")
TITLE = "【测试】Python 协程全景解析（自动发布探针）"

captured = []


def on_request(req):
    u = req.url
    if "juejin.cn" not in u:
        return
    if not any(k in u for k in ("content_api", "article_api", "content/v1")):
        return
    method = req.method
    body = None
    try:
        if method in ("POST", "PUT"):
            body = req.post_data
    except Exception:
        body = "<unreadable>"
    captured.append({"method": method, "url": u, "post_data": body,
                    "ts": time.time()})


def on_response(resp):
    u = resp.url
    if "content_api" not in u and "article_api" not in u:
        return
    try:
        body = resp.text()
    except Exception:
        body = "<unreadable>"
    entry = captured[-1] if captured else None
    if entry and entry.get("url") == u:
        entry["status"] = resp.status
        entry["resp"] = body[:500]
    else:
        captured.append({"method": "RESP", "url": u, "status": resp.status,
                         "resp": body[:500], "ts": time.time()})


def main():
    ad = JuejinAdapter()
    br = BuiltinBrowser("juejin", "default", headless=True)
    page = br.start().new_page()
    page.on("request", on_request)
    page.on("response", on_response)

    # 登录态
    page.goto(ad.home_url, timeout=60000, wait_until="domcontentloaded")
    time.sleep(2)
    if not ad.check_auth(page):
        print("掘金未登录，退出")
        return

    print("=== 1. 先创建草稿（走 API，确保有 draft_id 可填）===")
    AID = "2608"
    API = "https://api.juejin.cn"
    draft = ad.api_post(
        page,
        f"{API}/content_api/v1/article_draft/create?aid={AID}&spider=0",
        {
            "category_id": "6809637769959178254",  # 后端
            "tag_ids": ["7104"],
            "link_url": "",
            "cover_image": "",
            "title": TITLE,
            "brief_content": "探针",
            "edit_type": 10,
            "html_content": "deprecated",
            "mark_content": CONTENT_MD,
            "theme_ids": [],
        },
    )
    draft_id = (draft.get("data") or {}).get("id")
    print(f"draft_id = {draft_id}")

    print("=== 2. 进入编辑器 ===")
    page.goto(f"https://juejin.cn/editor/drafts/{draft_id}",
              timeout=60000, wait_until="domcontentloaded")
    time.sleep(5)

    print("=== 3. 点击顶部 发布 按钮（UI 面板）===")
    # 发布按钮可能有多层，逐个试
    clicked = False
    for sel in ['button.xitu-btn:not(.btn-drafts)', '.article-bar__publish button',
                'button:has-text("发布")']:
        try:
            btns = page.locator(sel)
            for i in range(btns.count()):
                b = btns.nth(i)
                if b.is_visible():
                    b.click(timeout=5000)
                    clicked = True
                    print(f"   点了 {sel} (第 {i} 个)")
                    break
            if clicked:
                break
        except Exception:
            continue
    time.sleep(4)

    # 确认面板真的打开了
    panel_open = page.evaluate("""() => {
        const all = document.querySelectorAll('input');
        return Array.from(all).filter(inp =>
            inp.placeholder && inp.placeholder.includes('标签')
        ).length;
    }""")
    print(f"   面板里 '标签' 输入框数量: {panel_open}")

    print("=== 4. 在发布面板里填 tag 搜索 ===")
    # 先把标题写进面板的标题输入框（如果有的话）
    try:
        title_inp = page.locator('input[placeholder*="文章标题"]')
        if title_inp.count():
            title_inp.fill(TITLE, timeout=5000)
            print("   标题填入 OK")
    except Exception as e:
        print(f"   标题填入失败: {str(e)[:60]}")

    # 先 dump 发布面板结构
    try:
        panel_info = page.evaluate("""() => {
            const out = {tagInputs: [], tagSearchInputs: [], allInputs: [], allButtons: []};
            document.querySelectorAll('input').forEach(inp => {
                out.allInputs.push({ph: inp.placeholder, cls: inp.className,
                                    visible: !!(inp.offsetWidth || inp.offsetHeight),
                                    rect: inp.getBoundingClientRect()});
            });
            document.querySelectorAll('button').forEach(b => {
                out.allButtons.push({txt: b.innerText.trim().slice(0,30),
                                     cls: b.className.slice(0,80),
                                     disabled: b.disabled,
                                     visible: !!(b.offsetWidth || b.offsetHeight)});
            });
            return out;
        }""")
        print("  输入框:", json.dumps([i for i in panel_info['allInputs'] if i['visible']], ensure_ascii=False)[:600])
        print("  按钮:", json.dumps([b for b in panel_info['allButtons'] if b['visible']], ensure_ascii=False)[:600])
    except Exception as e:
        print(f"  dump 面板失败: {str(e)[:80]}")
    time.sleep(1)

    # 找可见的 tag 输入框（placeholder 含 "标签" 或 "搜索"）
    tag_input = None
    for inp in page.query_selector_all("input"):
        ph = (inp.get_attribute("placeholder") or "").strip()
        if any(k in ph for k in ("标签", "搜索", "tag", "搜索标签")):
            if inp.is_visible():
                tag_input = inp
                break
    if tag_input:
        tag_input.click(timeout=5000)
        time.sleep(1)
    else:
        print("  没找到可见 tag 输入框，尝试强制显示并点 .tag-input")
        page.evaluate("""() => {
            document.querySelectorAll('.tag-input').forEach(el => {
                const s = getComputedStyle(el);
                if (s.display === 'none' || s.visibility === 'hidden') {
                    el.style.display = 'block';
                    el.style.visibility = 'visible';
                }
            });
        }""")
        time.sleep(1)
        try:
            tag_input = page.locator(".tag-input").first
            tag_input.click(timeout=5000, force=True)
        except Exception as e2:
            print(f"  强制点 .tag-input 也失败: {str(e2)[:80]}")
            tag_input = None
    if tag_input:
        page.keyboard.type("Python", delay=80)
        time.sleep(3)
        # 选第一个候选项（dropdown 列表 / 选项）
        try:
            cand = page.locator(".tag-input ul li, .tag-input [class*=option], "
                                ".el-select-dropdown__item, .tag-search-item, "
                                "[class*=dropdown] li, [class*=list] li")
            first = cand.first
            first.click(timeout=5000)
            time.sleep(2)
            print("   选中 tag 候选项 OK")
        except Exception as e:
            # 再尝试回车确认
            try:
                page.keyboard.press("Enter")
                time.sleep(2)
                print("   用 Enter 确认 tag")
            except Exception:
                print(f"   候选项没点到且 Enter 也失败: {str(e)[:60]}")

    print("=== 5. 点 确定并发布 ===")
    # 清掉当前 captured 看这一步真正发了什么
    captured.clear()
    # 先 dump 按钮状态
    btn_state = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('button').forEach(b => {
            const t = b.innerText.trim();
            if (t && (t.includes('发布') || t.includes('确定') || t.includes('确认'))) {
                out.push({txt: t, cls: b.className.slice(0,80),
                          disabled: b.disabled,
                          visible: !!(b.offsetWidth || b.offsetHeight)});
            }
        });
        return out;
    }""")
    print("  相关按钮:", json.dumps(btn_state, ensure_ascii=False)[:400])
    try:
        btn = page.locator("button:has-text('确定并发布')").first
        btn.click(timeout=8000)
        print("  点击 确定并发布 OK")
    except Exception as e:
        # 兜底：找 .ui-btn.btn.primary
        try:
            page.locator("button.ui-btn.btn.primary").last.click(timeout=8000)
            print("  点击 .ui-btn.btn.primary (兜底) OK")
        except Exception as e2:
            print(f"  发布按钮点不到: {str(e)[:80]} / {str(e2)[:80]}")
    time.sleep(3)

    print("=== 5.5 看点击后是否出现新按钮（可能 确定→发布 两步）===")
    new_btn_state = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('button').forEach(b => {
            const t = b.innerText.trim();
            if (t && (t.includes('发布') || t.includes('确定') || t.includes('确认') || t.includes('完成'))) {
                out.push({txt: t, cls: b.className.slice(0,80),
                          disabled: b.disabled,
                          visible: !!(b.offsetWidth || b.offsetHeight)});
            }
        });
        return out;
    }""")
    print("  新按钮:", json.dumps(new_btn_state, ensure_ascii=False)[:500])
    # 如果有"发布"按钮且可见，再点一次
    for b in new_btn_state:
        if b["txt"].strip() in ("发布", "确定发布", "发 布") and b["visible"] and not b["disabled"]:
            try:
                page.locator(f"button:has-text('{b['txt'].strip()}')").first.click(timeout=5000)
                print(f"   点了二次按钮: {b['txt']}")
                time.sleep(3)
            except Exception:
                pass
            break
    time.sleep(10)

    print(f"=== 6. 抓到 {len(captured)} 个请求 ===")
    for i, c in enumerate(captured):
        m = c.get("method")
        u = c.get("url", "")
        body = c.get("post_data") or ""
        status = c.get("status", "?")
        resp = (c.get("resp") or "")[:200]
        print(f"  [{i}] {m} {u}")
        if body:
            print(f"      body: {body[:400]}")
        print(f"      status={status} resp: {resp}")

    # 7. 看 URL 是否跳到 /post/
    time.sleep(5)
    print(f"\n最终 URL: {page.url}")
    if "/post/" in page.url:
        print("✅ 发布成功，article 页已打开")
    # 8. 用 article_draft/get 查一下草稿状态
    try:
        d2 = ad.api_get(page,
                        f"https://api.juejin.cn/content_api/v1/article_draft/get?aid=2608&id={draft_id}")
        print(f"\n草稿状态: article_id={(d2.get('data') or {}).get('article_id')}, "
              f"status={(d2.get('data') or {}).get('status')}")
    except Exception as e:
        print(f"\n草稿状态查询失败: {str(e)[:80]}")

    br.close()


if __name__ == "__main__":
    main()
