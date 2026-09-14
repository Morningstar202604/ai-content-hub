# -*- coding: utf-8 -*-
"""掘金适配器：发布 + 原地更新 + 列表。

平台专属常量都在这上面，掘金改版了就改这一块。
"""

import time

from core.adapters.base import PlatformAdapter, PlatformError, register

AID = "2608"
API = "https://api.juejin.cn"

# 分类 ID（掘金官方值）。若失效，打开 juejin.cn/editor/drafts/new 抓一下分类下拉即可更新
CATEGORIES = {
    "前端": "6809637767543259144",
    "后端": "6809637769959178254",
    "android": "6809635626879549454",
    "ios": "6809635626951802894",
    "人工智能": "6809637771511070734",
    "开发工具": "6809637776263217166",
    "代码人生": "6809637772874219534",
    "阅读": "6809637773935378440",
}
DEFAULT_CATEGORY = "后端"


def _click_text(page, texts, timeout=8000):
    for t in texts:
        try:
            page.click(f"text={t}", timeout=timeout)
            return t
        except Exception:
            continue
    raise PlatformError(f"页面上找不到这些按钮: {texts}")


@register
class JuejinAdapter(PlatformAdapter):
    id = "juejin"
    name = "稀土掘金"
    login_url = "https://juejin.cn/login"
    home_url = "https://juejin.cn/creator/home"
    list_url = "https://juejin.cn/creator/content/article"
    new_url = "https://juejin.cn/editor/drafts/new"

    # ---------------- 登录态 ----------------

    def check_auth(self, page) -> bool:
        try:
            data = self.api_get(page, f"{API}/user_api/v1/user/get?aid={AID}")
            return bool((data.get("data") or {}).get("user_id"))
        except Exception:
            return False

    def _user_id(self, page):
        data = self.api_get(page, f"{API}/user_api/v1/user/get?aid={AID}")
        uid = (data.get("data") or {}).get("user_id")
        if not uid:
            raise PlatformError("拿不到 user_id，登录态可能失效")
        return uid

    # ---------------- 列表 ----------------

    def list_articles(self, page, limit=50):
        uid = self._user_id(page)
        page.goto(self.list_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)  # SPA 加载

        # 编辑链接从 DOM 抓，不猜 —— 标题和 href 对齐存起来
        edit_map = {}
        try:
            items = page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('a[href*="/editor/"]').forEach(a => {
                    const row = a.closest('li, tr, div[class*="item"]');
                    const t = (row && row.innerText || a.innerText || '').split('\\n')[0].trim();
                    if (t) out.push({title: t, href: a.getAttribute('href')});
                });
                return out;
            }""")
            for it in items:
                if it["href"] and it["title"]:
                    edit_map[it["title"]] = it["href"]
        except Exception:
            pass

        data = self.api_get(
            page, f"{API}/content_api/v1/article/query_list"
                  f"?aid={AID}&user_id={uid}&sort_type=2&cursor=0")
        rows = data.get("data") or []
        out = []
        for a in rows[:limit]:
            title = (a.get("title") or "").strip()
            aid_ = a.get("article_id") or a.get("article_info", {}).get("article_id")
            info = a.get("article_info") or {}
            href = edit_map.get(title)
            edit_url = ("https://juejin.cn" + href) if href and href.startswith("/") else href
            out.append({
                "post_id": aid_,
                "title": title,
                "url": f"https://juejin.cn/post/{aid_}" if aid_ else "",
                "edit_url": edit_url or "",
                "status": "published" if info.get("status") == 2 else "draft",
                "stats": {
                    "view": info.get("view_count", 0),
                    "digg": info.get("digg_count", 0),
                    "comment": info.get("comment_count", 0),
                },
            })
        return out

    # ---------------- 发布 ----------------

    def publish(self, page, article, options=None):
        options = options or {}
        cat = options.get("category") or DEFAULT_CATEGORY
        cat_id = CATEGORIES.get(cat) or CATEGORIES[DEFAULT_CATEGORY]
        brief = (article.get("summary")
                 or (article.get("content_md", "")[:100].replace("\n", " ")))

        payload = {
            "category_id": cat_id,
            "tag_ids": [],
            "link_url": "",
            "cover_image": article.get("cover") or "",
            "title": article["title"],
            "brief_content": brief,
            "edit_type": 10,                      # 10 = Markdown
            "html_content": "deprecated",
            "mark_content": article.get("content_md", ""),
            "theme_ids": [],
        }
        draft = self.api_post(
            page, f"{API}/content_api/v1/article_draft/create?aid={AID}&spider=0", payload)
        draft_id = (draft.get("data") or {}).get("id")
        if not draft_id:
            raise PlatformError(f"创建草稿失败: {draft}")

        if options.get("draft_only"):
            return {"post_id": draft_id,
                    "post_url": "",
                    "edit_url": f"https://juejin.cn/editor/drafts/{draft_id}",
                    "draft_only": True}

        res = self.api_post(page, f"{API}/content_api/v1/article/publish?aid={AID}&spider=0",
                            {"draft_id": draft_id, "sync_to_org": False, "column_ids": []})
        article_id = (res.get("data") or {}).get("article_id") or draft_id
        return {
            "post_id": article_id,
            "post_url": f"https://juejin.cn/post/{article_id}",
            "edit_url": f"https://juejin.cn/editor/drafts/{draft_id}",
            "draft_only": False,
        }

    # ---------------- 原地更新 ----------------

    def update(self, page, pub, article):
        edit_url = pub.get("edit_url") or f"https://juejin.cn/editor/drafts/{pub.get('post_id')}"
        page.goto(edit_url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector(".CodeMirror", timeout=30000)
        time.sleep(2)

        # 标题
        try:
            title_input = page.query_selector('input[placeholder*="标题"]')
            if title_input:
                title_input.click()
                page.keyboard.press("Control+A")
                page.keyboard.type(article["title"])
        except Exception:
            pass

        self.set_editor_content(page, article.get("content_md", ""))
        time.sleep(1)

        _click_text(page, ["发布", "发布文章"])
        time.sleep(1.5)
        _click_text(page, ["确定并发布", "确认发布", "并发布"])
        time.sleep(4)
        return True
