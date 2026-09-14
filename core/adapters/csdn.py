# -*- coding: utf-8 -*-
"""CSDN 适配器。

CSDN 的发布接口走阿里云网关签名（X-Ca-Signature），逆向成本高还容易失效，
所以这里统一走**编辑器 UI 操作**——比签名稳，也和真人操作等价。
代价是慢一点，但自动化本来也不赶这几秒。
"""

import time

from core.adapters.base import PlatformAdapter, PlatformError, register

HOME_API = "https://blog.csdn.net/community/home-api/v1/get-business-list"


def _click_text(page, texts, timeout=8000):
    for t in texts:
        try:
            page.click(f"text={t}", timeout=timeout)
            return t
        except Exception:
            continue
    raise PlatformError(f"页面上找不到这些按钮: {texts}")


@register
class CSDNAdapter(PlatformAdapter):
    id = "csdn"
    name = "CSDN"
    login_url = "https://passport.csdn.net/login"
    home_url = "https://mp.csdn.net/mp_blog/manage/article"
    list_url = "https://mp.csdn.net/mp_blog/manage/article"
    new_url = "https://editor.csdn.net/md/"

    # ---------------- 登录态 ----------------

    def check_auth(self, page) -> bool:
        # 注意：CSDN 未登录时访问 mp 后台**不跳转**（返回空壳 SPA），
        # 光看 URL 会误判成已登录。必须再验一次能不能读到用户名。
        try:
            page.goto(self.home_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)
            if "passport.csdn.net" in page.url or "/login" in page.url:
                return False
            return bool(self._username(page))
        except Exception:
            return False

    def _username(self, page):
        for c in page.context.cookies():
            if c["name"] in ("UserName", "username") and c["value"]:
                return c["value"]
        raise PlatformError("读不到 CSDN 用户名，登录态可能失效")

    # ---------------- 列表 ----------------

    def list_articles(self, page, limit=50):
        user = self._username(page)
        data = self.api_get(
            page, f"{HOME_API}?page=1&size={min(limit, 100)}&businessType=blog"
                  f"&username={user}&noMore=false")
        rows = ((data.get("data") or {}).get("list")) or []
        out = []
        for a in rows:
            aid = str(a.get("articleId") or a.get("id") or "")
            out.append({
                "post_id": aid,
                "title": a.get("title", ""),
                "url": a.get("url") or (f"https://blog.csdn.net/{user}/article/details/{aid}"),
                "edit_url": f"https://editor.csdn.net/md/?articleId={aid}",
                "status": "published",
                "stats": {"view": a.get("viewCount", 0),
                          "digg": a.get("diggCount", 0),
                          "comment": a.get("commentCount", 0)},
            })
        return out

    # ---------------- 发布 ----------------

    def publish(self, page, article, options=None):
        options = options or {}
        page.goto(self.new_url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector(".CodeMirror", timeout=30000)
        time.sleep(2)

        # 标题
        try:
            ti = page.query_selector('input[placeholder*="标题"], .article-bar__title input')
            if ti:
                ti.click()
                page.keyboard.type(article["title"])
        except Exception:
            pass

        self.set_editor_content(page, article.get("content_md", ""))
        time.sleep(1)

        if options.get("draft_only"):
            _click_text(page, ["保存草稿", "存草稿"])
            time.sleep(2)
            return {"post_id": "", "post_url": "", "edit_url": page.url, "draft_only": True}

        _click_text(page, ["发布文章", "发布"])
        time.sleep(2)
        # 发布弹窗：摘要、标签、分类
        try:
            ta = page.query_selector('textarea[placeholder*="摘要"], .abstract textarea')
            if ta:
                ta.click()
                page.keyboard.type(article.get("summary") or article["title"])
        except Exception:
            pass
        _click_text(page, ["发布文章", "确定", "确认发布"])
        time.sleep(5)

        # 发布成功后 URL 会带上 articleId，从这儿取
        aid = ""
        if "articleId=" in page.url:
            aid = page.url.split("articleId=")[-1].split("&")[0]
        return {"post_id": aid,
                "post_url": f"https://blog.csdn.net/article/details/{aid}" if aid else "",
                "edit_url": f"https://editor.csdn.net/md/?articleId={aid}" if aid else page.url,
                "draft_only": False}

    # ---------------- 原地更新 ----------------

    def update(self, page, pub, article):
        edit_url = pub.get("edit_url")
        if not edit_url and pub.get("post_id"):
            edit_url = f"https://editor.csdn.net/md/?articleId={pub['post_id']}"
        if not edit_url:
            raise PlatformError("没有 edit_url 也没有 post_id，没法原地更新")

        page.goto(edit_url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector(".CodeMirror", timeout=30000)
        time.sleep(3)

        self.set_editor_content(page, article.get("content_md", ""))
        time.sleep(1)

        _click_text(page, ["发布文章", "发布"])
        time.sleep(2)
        _click_text(page, ["发布文章", "确定", "确认发布"])
        time.sleep(5)
        return True
