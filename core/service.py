# -*- coding: utf-8 -*-
"""业务层：把 文章库 × 内置浏览器 × 平台适配器 串起来。

AI 或者 REST API 调的都是这里的方法，不用碰浏览器细节。
"""

import json
from pathlib import Path

from core import db
from core.adapters.base import PlatformError, get_adapter
from core.browser import BuiltinBrowser, ensure_login, CaptchaPolicy, wait_human_captcha

ROOT = Path(__file__).resolve().parent.parent

# 导入即注册
from core.adapters import juejin, csdn, cnblogs  # noqa: F401

import random
import time


class Hub:
    def __init__(self, headless=True):
        self.conn = db.connect()
        self.headless = headless
        # 风控：平台间隔 + 文章间隔，别调太小，被限流了别来找我
        self.delay_platform = (8, 20)
        self.delay_article = (30, 90)
        # 遇到验证码时怎么处理：handoff=交人工 / abort=直接放弃
        self.on_captcha = "handoff"

    # ---------------- 账号 ----------------

    def login(self, platform, account="default", timeout=600, on_captcha=None):
        """扫码/过验证登录一次，登录态存进本地 profile，之后长期有效。"""
        ad = get_adapter(platform)
        # 纯协议平台不用开浏览器，直接验凭据
        if not ad.needs_browser:
            try:
                ok = ad.check_auth(None)
                db.upsert_account(self.conn, platform, account, "-",
                                  "logined" if ok else "offline")
                return ok, ("凭据有效（免登录 API）" if ok else "凭据无效，检查 config.json")
            except PlatformError as e:
                db.upsert_account(self.conn, platform, account, "-", "offline")
                return False, str(e)

        br = BuiltinBrowser(platform, account, headless=False)  # 登录必须有头
        try:
            ok, msg = ensure_login(br, ad.login_url, ad.check_auth, timeout=timeout,
                                   on_captcha=on_captcha or self.on_captcha)
            db.upsert_account(self.conn, platform, account,
                              str(br.profile_dir), "logined" if ok else "offline")
            return ok, msg
        finally:
            br.close()

    def check(self, platform, account="default"):
        ad = get_adapter(platform)
        if not ad.needs_browser:
            try:
                ok = ad.check_auth(None)
            except PlatformError:
                ok = False
            db.upsert_account(self.conn, platform, account, "-",
                              "logined" if ok else "offline")
            return ok
        br = BuiltinBrowser(platform, account, headless=self.headless)
        try:
            page = br.new_page()
            ok = ad.check_auth(page)
            # 登录态正常但页面在弹验证码，说明"能登但不一定能操作"，得告诉用户
            if ok and CaptchaPolicy.detect(page):
                db.upsert_account(self.conn, platform, account, str(br.profile_dir),
                                  "logined")
                return ok
            db.upsert_account(self.conn, platform, account, str(br.profile_dir),
                              "logined" if ok else "offline")
            return ok
        finally:
            br.close()

    def diagnose(self, platform):
        """排查端点：这平台到底该怎么接入、验证码怎么过，一目了然。"""
        from core.browser import ensure_display
        ad = get_adapter(platform)
        info = {
            "platform": platform, "name": ad.name,
            "需要浏览器": ad.needs_browser,
            "登录页": ad.login_url,
            "反检测": "已启用（隐藏 webdriver / 伪装 WebGL 与硬件指纹 / 拟人输入鼠标）",
        }
        if platform in CaptchaPolicy.API_FIRST:
            info["推荐接入"] = CaptchaPolicy.API_FIRST[platform]
        info["验证码策略"] = (
            "免登 API，不会遇到验证码" if not ad.needs_browser else
            "L1 反检测降低触发 → L2 登录态持久化 → L3 弹了就半自动试一次，不行转人工"
        )
        if ad.needs_browser:
            info["有头显示"] = ensure_display() or "不可用（装 xvfb：apt install -y xvfb）"
        return info

    def bootstrap_cnblogs(self, username, password, account="default",
                          timeout=600, on_captcha="handoff"):
        """浏览器登录博客园，登录后自动抠出 MetaWeblog 三件套写进 config.json。

        这是取代「让用户手贴令牌」的正确路径：账号+密码登一次，登录态存盘，
        设置页里把 endpoint/username/token 自动抠出来，之后发布走纯协议。
        """
        from core.browser import BuiltinBrowser
        from core.cnblogs_login import login_browser, extract_metaweblog
        from core.browser import ensure_display

        ensure_display()
        br = BuiltinBrowser("cnblogs", account, headless=False)  # 登录必须有头
        try:
            r = login_browser(br, username, password,
                              on_captcha=on_captcha, timeout=timeout)
            if r.get("outcome") != "success":
                db.upsert_account(self.conn, "cnblogs", account, str(br.profile_dir),
                                  "offline")
                return r
            # 登录成功，抠令牌（username 用登录名，别拿 blogApp 冒充）
            page = br.new_page()
            mw = extract_metaweblog(page, save_to=str(ROOT / "config.json"),
                                    login_username=username)
            page.close()
            db.upsert_account(self.conn, "cnblogs", account, str(br.profile_dir),
                              "logined")
            r["metaweblog"] = mw
            return r
        finally:
            br.close()
        """打开平台页面，如果弹验证码就地处理：先半自动，不行转人工。

        这是给"登录时弹了验证码，想单独处理一下"准备的入口。
        """
        from core.browser import CaptchaPolicy, wait_human_captcha
        ad = get_adapter(platform)
        if not ad.needs_browser:
            return {"ok": True, "msg": f"{platform} 走免登 API，不会有验证码"}
        br = BuiltinBrowser(platform, account, headless=False)
        try:
            page = br.new_page()
            page.goto(ad.login_url, timeout=60000, wait_until="domcontentloaded")
            import time as _t
            _t.sleep(3)
            kind = CaptchaPolicy.detect(page)
            if not kind:
                return {"ok": True, "msg": "当前页面没有验证码"}
            ok, info = wait_human_captcha(page, platform, timeout=wait)
            return {"ok": ok, "kind": kind, **info}
        finally:
            br.close()

    def accounts(self):
        return [dict(r) for r in db.list_accounts(self.conn)]

    # ---------------- 文章 ----------------

    def create(self, title, content_md="", **kw):
        return db.create_article(self.conn, title, content_md, **kw)

    def edit(self, article_id, **kw):
        """改文章。内容一改，已发布实例自动标成 pending，等 sync_pending 去同步。"""
        ok = db.update_article(self.conn, article_id, **kw)
        pending = db.get_pending_updates(self.conn)
        return ok, len(pending)

    def get(self, article_id):
        r = db.get_article(self.conn, article_id)
        return dict(r) if r else None

    def list(self, status=None, limit=100):
        return [dict(r) for r in db.list_articles(self.conn, status, limit)]

    def search(self, keyword):
        return [dict(r) for r in db.search_articles(self.conn, keyword)]

    def import_md(self, path, title=None, tags=""):
        from pathlib import Path
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="replace")
        if text.startswith("---"):  # 顺手吃掉 front-matter 当元数据
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].splitlines():
                    if line.lower().startswith("title:"):
                        title = title or line.split(":", 1)[1].strip()
                    if line.lower().startswith("tags:"):
                        tags = tags or line.split(":", 1)[1].strip().strip("[]")
                text = parts[2]
        title = title or p.stem
        aid = db.create_article(self.conn, title, text.lstrip("\n"),
                                tags=tags, source="import")
        return aid

    # ---------------- 发布 / 更新 ----------------

    def _with_adapter(self, platform, account, fn):
        """统一入口：需要浏览器的开浏览器，走协议的直接调。"""
        ad = get_adapter(platform)
        if not ad.needs_browser:
            if not ad.check_auth(None):
                raise PlatformError(f"{platform} 凭据无效，检查 config.json")
            return fn(ad, None)

        br = BuiltinBrowser(platform, account, headless=self.headless)
        try:
            page = br.new_page()
            if not ad.check_auth(page):
                raise PlatformError(f"{platform}({account}) 未登录，先跑 login")
            return fn(ad, page)
        finally:
            br.close()

    # ---------------- AI ----------------

    def ai_write(self, topic, style="", words=2000, tags_hint="", publish_to=None):
        """AI 写一篇并入库。传了 publish_to 就顺手发出去。"""
        from core import ai as ai_mod
        art = ai_mod.write_article(topic, style, words, tags_hint)
        aid = db.create_article(self.conn, art["title"], art["content_md"],
                                summary=art["summary"], tags=art["tags"],
                                source="ai", ai_model=art["ai_model"],
                                status="draft")
        out = {"id": aid, "title": art["title"], "summary": art["summary"],
               "tags": art["tags"], "chars": len(art["content_md"])}
        if publish_to:
            out["publish"] = self.publish(aid, publish_to)
        return out

    def ai_rewrite(self, article_id, instruction, publish_to=None):
        """AI 改写已有文章，改完自动标记待同步。"""
        from core import ai as ai_mod
        art = self.get(article_id)
        if not art:
            raise ValueError(f"文章 {article_id} 不存在")
        new_md = ai_mod.rewrite(art["content_md"], instruction)
        db.update_article(self.conn, article_id, content_md=new_md)
        out = {"id": article_id, "chars": len(new_md),
               "pending_sync": len(db.get_pending_updates(self.conn))}
        if publish_to:
            out["update"] = self.update(article_id, publish_to)
        return out

    def ai_polish(self, article_id):
        from core import ai as ai_mod
        art = self.get(article_id)
        if not art:
            raise ValueError(f"文章 {article_id} 不存在")
        new_md = ai_mod.polish(art["content_md"])
        db.update_article(self.conn, article_id, content_md=new_md)
        return {"id": article_id, "pending_sync": len(db.get_pending_updates(self.conn))}

    def ai_ready(self):
        from core import ai as ai_mod
        return ai_mod.is_ready()

    def publish(self, article_id, platforms, account="default", draft_only=False):
        art = self.get(article_id)
        if not art:
            raise ValueError(f"文章 {article_id} 不存在")
        results = []
        for pf in platforms:
            job = db.add_job(self.conn, "publish", article_id, pf)
            try:
                def _do(ad, page, pf=pf):
                    return ad.publish(page, art, {"draft_only": draft_only})
                r = self._with_adapter(pf, account, _do)
                db.upsert_publication(self.conn, article_id, pf, account,
                                      post_id=r.get("post_id", ""),
                                      post_url=r.get("post_url", ""),
                                      edit_url=r.get("edit_url", ""),
                                      status="ok",
                                      draft_only=1 if r.get("draft_only") else 0,
                                      published_at=db.now())
                db.update_article(self.conn, article_id, status="published")
                db.finish_job(self.conn, job, True, "发布成功")
                results.append({"platform": pf, "ok": True, **r})
            except Exception as e:
                db.upsert_publication(self.conn, article_id, pf, account,
                                      status="failed", last_error=str(e)[:300])
                db.finish_job(self.conn, job, False, str(e)[:300])
                results.append({"platform": pf, "ok": False, "error": str(e)})
            if pf != platforms[-1]:
                time.sleep(random.uniform(*self.delay_platform))
        return results

    def update(self, article_id, platforms=None, account="default"):
        """原地更新：打开各平台的编辑页改内容，改完就是更新，不是新发一篇。"""
        art = self.get(article_id)
        if not art:
            raise ValueError(f"文章 {article_id} 不存在")
        pubs = db.get_publications(self.conn, article_id=article_id)
        if platforms:
            pubs = [p for p in pubs if p["platform"] in platforms]
        pubs = [p for p in pubs if p["post_id"] or p["edit_url"]]
        if not pubs:
            return {"skipped": "没有已发布实例可更新，先 publish"}

        results = []
        for p in pubs:
            pf = p["platform"]
            job = db.add_job(self.conn, "update", article_id, pf)
            try:
                def _do(ad, page, p=p):
                    return ad.update(page, dict(p), art)
                self._with_adapter(pf, account, _do)
                db.upsert_publication(self.conn, article_id, pf, account,
                                      status="ok", last_error="",
                                      draft_only=0, updated_at=db.now())
                db.finish_job(self.conn, job, True, "原地更新成功")
                results.append({"platform": pf, "ok": True})
            except Exception as e:
                db.upsert_publication(self.conn, article_id, pf, account,
                                      last_error=str(e)[:300])
                db.finish_job(self.conn, job, False, str(e)[:300])
                results.append({"platform": pf, "ok": False, "error": str(e)})
            time.sleep(random.uniform(*self.delay_article))
        return results

    def sync_pending(self, account="default"):
        """把内容变更同步到所有已发布平台——AI 改完文章点这个就完事。"""
        rows = db.get_pending_updates(self.conn)
        out = []
        for r in rows:
            out.append({"article_id": r["article_id"], "title": r["title"],
                        **{p["platform"]: p for p in []}})
            res = self.update(r["article_id"],
                              platforms=[r["platform"]], account=account)
            out[-1]["result"] = res.get("results") if isinstance(res, dict) else res
        return out

    def refresh(self, platform, account="default", limit=50):
        """把平台上的文章列表抓回来入库，AI 才能"看见账号里有什么"。"""
        def _do(ad, page):
            return ad.list_articles(page, limit=limit)
        items = self._with_adapter(platform, account, _do)
        saved = 0
        for it in items:
            # 已有同 post_id 的更新，否则新建一条孤儿记录等人工关联
            row = self.conn.execute(
                "SELECT * FROM publications WHERE platform=? AND post_id=?",
                (platform, it["post_id"])).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE publications SET edit_url=?, post_url=?, stats=?, status='ok' WHERE id=?",
                    (it.get("edit_url", ""), it.get("url", ""),
                     json.dumps(it.get("stats", {}), ensure_ascii=False), row["id"]))
            else:
                aid = db.create_article(self.conn, it["title"], "",
                                        status="published", source="import")
                db.upsert_publication(self.conn, aid, platform, account,
                                      post_id=it["post_id"], post_url=it.get("url", ""),
                                      edit_url=it.get("edit_url", ""), status="ok",
                                      stats=json.dumps(it.get("stats", {}), ensure_ascii=False),
                                      draft_only=0)
            saved += 1
        self.conn.commit()
        return {"platform": platform, "count": len(items), "saved": saved, "items": items}

    def status(self):
        arts = self.conn.execute("SELECT COUNT(*) c FROM articles").fetchone()["c"]
        pubs = self.conn.execute("SELECT COUNT(*) c FROM publications").fetchone()["c"]
        ok = self.conn.execute(
            "SELECT COUNT(*) c FROM publications WHERE status='ok'").fetchone()["c"]
        pend = self.conn.execute(
            "SELECT COUNT(*) c FROM publications WHERE status='pending'").fetchone()["c"]
        return {"articles": arts, "publications": pubs, "published": ok,
                "pending_sync": pend, "accounts": self.accounts()}
