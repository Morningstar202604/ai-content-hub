# -*- coding: utf-8 -*-
"""简书适配器：作者后台 API 全套（建文 → 写内容 → 公开发布）。

简书作者接口只要 cookie 不要签名，页面上下文 fetch 即可，比 UI 稳得多。
接口序列参考 MultiPost-Extension 实测实现。
"""

import time

from core.adapters.base import (
    PlatformAdapter,
    PlatformError,
    md_to_html,
    register,
)

API = "https://www.jianshu.com"


@register
class JianshuAdapter(PlatformAdapter):
    id = "jianshu"
    name = "简书"
    login_url = "https://www.jianshu.com/sign_in"
    home_url = "https://www.jianshu.com/"
    list_url = "https://www.jianshu.com/writer"
    new_url = "https://www.jianshu.com/writer#/notes/new"

    # ---------------- 登录态 ----------------

    def check_auth(self, page) -> bool:
        # 作者接口未登录会 302 到登录页 HTML，登录后返回 JSON 数组
        try:
            data = self.api_get(page, f"{API}/author/notebooks")
            return isinstance(data, list)
        except Exception:
            return False

    # ---------------- 列表 ----------------

    def list_articles(self, page, limit=50):
        out = []
        notebooks = self.api_get(page, f"{API}/author/notebooks")
        for nb in notebooks or []:
            try:
                notes = self.api_get(page, f"{API}/author/notebooks/{nb['id']}/notes")
            except Exception:
                continue
            for n in notes or []:
                out.append({
                    "post_id": str(n.get("id", "")),
                    "title": (n.get("title") or "").strip(),
                    "url": f"https://www.jianshu.com/p/{n['slug']}" if n.get("slug") else "",
                    "edit_url": f"{API}/writer#/notebooks/{nb['id']}/notes/{n['id']}/writing",
                    # 8=草稿? 简书 last_updated_in_... 无公开枚举，slug 有值就当已公开
                    "status": "published" if n.get("slug") else "draft",
                    "stats": {"view": n.get("views_count", 0),
                              "digg": n.get("likes_count", 0),
                              "comment": n.get("comments_count", 0)},
                })
                if len(out) >= limit:
                    return out
        return out

    # ---------------- 发布 ----------------

    def publish(self, page, article, options=None):
        options = options or {}
        notebooks = self.api_get(page, f"{API}/author/notebooks")
        if not notebooks:
            raise PlatformError("简书没有可用笔记本，先在简书上手动建一个")
        nb_id = notebooks[0]["id"]

        note = self.api_post(page, f"{API}/author/notes",
                             {"notebook_id": nb_id, "title": article["title"],
                              "at_bottom": False})
        note_id = note.get("id")
        if not note_id:
            raise PlatformError(f"简书创建文章失败: {str(note)[:200]}")

        self.api_put(page, f"{API}/author/notes/{note_id}",
                     {"id": note_id, "autosave_control": 1,
                      "title": article["title"],
                      "content": md_to_html(article.get("content_md", ""))})

        if options.get("draft_only"):
            return {"post_id": str(note_id), "post_url": "",
                    "edit_url": f"{API}/writer#/notebooks/{nb_id}/notes/{note_id}/writing",
                    "draft_only": True}

        # 转为公开文章；公开后响应里带 slug（/p/{slug} 是对外地址）
        pub = self.api_post(page, f"{API}/author/notes/{note_id}/publicize", {})
        slug = (pub.get("slug") if isinstance(pub, dict) else None) or \
               (note.get("slug") if isinstance(note, dict) else None)
        time.sleep(1)
        return {"post_id": str(note_id),
                "post_url": f"https://www.jianshu.com/p/{slug}" if slug else "",
                "edit_url": f"{API}/writer#/notebooks/{nb_id}/notes/{note_id}/writing",
                "draft_only": False}

    # ---------------- 原地更新 ----------------

    def update(self, page, pub, article):
        note_id = pub.get("post_id")
        if not note_id:
            raise PlatformError("简书原地更新需要 post_id，先重新发布一次")
        self.api_put(page, f"{API}/author/notes/{note_id}",
                     {"id": int(note_id), "autosave_control": 1,
                      "title": article["title"],
                      "content": md_to_html(article.get("content_md", ""))})
        time.sleep(1)
        return True
