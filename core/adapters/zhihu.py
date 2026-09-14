# -*- coding: utf-8 -*-
"""知乎适配器：专栏文章，走 UI（编辑器注入 + 点发布）。

为什么不用 API：知乎的 /api/v4/* 大多要求 x-zse-96 签名（前端 JS 生成），
裸 fetch 会被拒。走页面 UI 让前端自己发请求，签名/风控都由它处理，反而最稳。

选择器参考社区实测（MultiPost-Extension），知乎改版后用 dump_dom 重新抓。
"""

import time

from core.adapters.base import (
    PASTE_HTML_JS,
    PlatformAdapter,
    PlatformError,
    md_to_html,
    register,
)

TITLE_SEL = 'textarea[placeholder*="请输入标题"]'
EDITOR_SEL = 'div[data-contents="true"]'   # Draft.js 编辑器根节点


def _click_button(page, texts, timeout=8000):
    """点文本匹配的按钮（知乎按钮样式多，按文本找最稳）"""
    for t in texts:
        try:
            page.locator(f"button:has-text(\"{t}\")").first.click(timeout=timeout)
            return t
        except Exception:
            continue
    raise PlatformError(f"页面上找不到按钮: {texts}")


@register
class ZhihuAdapter(PlatformAdapter):
    id = "zhihu"
    name = "知乎"
    login_url = "https://www.zhihu.com/signin?next=%2F"
    home_url = "https://zhuanlan.zhihu.com/write"
    list_url = "https://www.zhihu.com/creator"   # 创作中心（内容管理在里面）
    new_url = "https://zhuanlan.zhihu.com/write"

    # ---------------- 登录态 ----------------

    DOMAIN = "zhihu.com"

    def check_auth(self, page) -> bool:
        # 判定靠 URL：未登录访问写作页会被平台踢回 /signin。
        # 注意：页面已在知乎域内时绝不 goto —— ensure_login 轮询期间
        # 用户可能正在登录页上扫码，反复导航会把扫码动作打断
        try:
            url = page.url
            if self.DOMAIN not in url:
                page.goto(self.new_url, timeout=60000, wait_until="domcontentloaded")
                url = page.url
                time.sleep(1.5)
            return "/signin" not in url
        except Exception:
            return False

    # ---------------- 列表 ----------------

    def list_articles(self, page, limit=50):
        # 创作中心的内容管理是前端渲染 + 内部接口，结构随版本漂移，先占位
        raise PlatformError("知乎已发文章列表暂未适配（编辑器发布可用）。"
                            "如有需要，跑一次 dump_dom 抓创作中心结构后补充")

    # ---------------- 发布 ----------------

    def publish(self, page, article, options=None):
        options = options or {}
        page.goto(self.new_url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector(TITLE_SEL, timeout=30000)
        time.sleep(2)

        # 标题（知乎限 100 字）
        page.fill(TITLE_SEL, article["title"][:100])

        # 正文：HTML 粘贴进 Draft.js 编辑器（支持代码块/表格）
        html = md_to_html(article.get("content_md", ""))
        ok = page.evaluate(PASTE_HTML_JS, [EDITOR_SEL, html])
        if not ok:
            self.save_debug(page, "zhihu_no_editor")
            raise PlatformError("找不到知乎正文编辑器（可能改版或未登录）")
        time.sleep(4)  # 等编辑器消化内容 + 自动保存

        if options.get("draft_only"):
            # 知乎编辑器自动存草稿，但没有公开的草稿 ID 可拿 —— 不点发布，交人工确认
            return {"post_id": "", "post_url": "", "edit_url": self.new_url,
                    "draft_only": True}

        _click_button(page, ["发布"])
        time.sleep(2)

        # 可能弹发布设置（首次发布弹开通/话题选择），有「确认/发布」就再点一次
        try:
            _click_button(page, ["确认发布", "确定", "发布"], timeout=5000)
        except Exception:
            pass

        # 发布成功后 URL 会跳到 /p/<id>
        deadline = time.time() + 30
        while time.time() < deadline:
            time.sleep(1.5)
            if "/p/" in page.url:
                post_id = page.url.rstrip("/").split("/p/")[-1].split("?")[0]
                return {"post_id": post_id, "post_url": f"https://zhuanlan.zhihu.com/p/{post_id}",
                        "edit_url": page.url, "draft_only": False}
        self.save_debug(page, "zhihu_publish_stuck")
        raise PlatformError("点了发布但 30 秒内没跳到文章页，可能弹了人工确认窗口，"
                            "去浏览器里手动确认后用「原地更新」补状态")

    # ---------------- 原地更新 ----------------

    def update(self, page, pub, article):
        # 已发布文章页右上角有「编辑」，进去后编辑器结构一致
        page.goto(pub.get("post_url") or pub.get("edit_url"),
                  timeout=60000, wait_until="domcontentloaded")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        _click_button(page, ["编辑"], timeout=10000)
        page.wait_for_selector(EDITOR_SEL, timeout=30000)
        time.sleep(2)

        try:
            page.fill(TITLE_SEL, article["title"][:100])
        except Exception:
            pass
        html = md_to_html(article.get("content_md", ""))
        page.evaluate(PASTE_HTML_JS, [EDITOR_SEL, html])
        time.sleep(4)

        # 编辑已发布文章的按钮是「保存并发布」；纯草稿是「发布」
        _click_button(page, ["保存并发布", "发布"])
        time.sleep(2)
        try:
            _click_button(page, ["确认发布", "确定"], timeout=5000)
        except Exception:
            pass
        time.sleep(3)
        return True
