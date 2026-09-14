# -*- coding: utf-8 -*-
"""REST API：AI 或你自己的脚本通过这个管整个中台。

启动：  python -m server.api     或     uvicorn server.api:app --port 8800
文档：  http://127.0.0.1:8800/docs
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

from core.service import Hub

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="AI 内容中台", version="0.2.0")
hub = Hub(headless=True)

# ---------------- 可选 API 鉴权 ----------------
# config.json 里配 "api_token": "一串随机字符串" 即启用：
# 除 /static 与根路径外，所有请求必须带 X-API-Token 头。默认不配 = 不启用（本地用）。
def _api_token():
    try:
        return (json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
                or {}).get("api_token") or ""
    except Exception:
        return ""


@app.middleware("http")
async def _auth(request, call_next):
    if request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
        token = _api_token()
        if token and request.headers.get("X-API-Token") != token \
                and not request.url.path.startswith("/static"):
            return JSONResponse({"detail": "无效的 API Token"}, status_code=401)
    return await call_next(request)

STATIC = Path(__file__).resolve().parent / "static"


@app.get("/", include_in_schema=False)
def index():
    """Web 管理界面，浏览器打开 http://127.0.0.1:8800 就是这个。"""
    return FileResponse(str(STATIC / "index.html"))


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class ArticleIn(BaseModel):
    title: str
    content_md: str = ""
    summary: str = ""
    tags: str = ""
    cover: str = ""
    status: str = "draft"
    source: str = "human"   # AI 写稿时由 service 显式传 ai，别默认标成 AI
    ai_model: str = ""


class ArticlePatch(BaseModel):
    title: Optional[str] = None
    content_md: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[str] = None
    cover: Optional[str] = None
    status: Optional[str] = None


class PublishIn(BaseModel):
    platforms: List[str]
    account: str = "default"
    draft_only: bool = False


class UpdateIn(BaseModel):
    platforms: Optional[List[str]] = None
    account: str = "default"


class ImportIn(BaseModel):
    path: str
    tags: str = ""


class AIWriteIn(BaseModel):
    topic: str
    style: str = ""
    words: int = 2000
    tags_hint: str = ""
    publish_to: Optional[List[str]] = None


class AIRewriteIn(BaseModel):
    instruction: str
    publish_to: Optional[List[str]] = None


@app.get("/status")
def status():
    return hub.status()


# ---------------- 文章 ----------------

@app.get("/articles")
def list_articles(status: str = None, limit: int = 100):
    return hub.list(status, limit)


@app.post("/articles")
def create_article(a: ArticleIn):
    return {"id": hub.create(**a.dict())}


@app.get("/articles/{aid}")
def get_article(aid: int):
    r = hub.get(aid)
    if not r:
        raise HTTPException(404, "文章不存在")
    return r


@app.put("/articles/{aid}")
def update_article(aid: int, patch: ArticlePatch):
    data = {k: v for k, v in patch.dict().items() if v is not None}
    ok, pending = hub.edit(aid, **data)
    return {"ok": ok, "pending_sync": pending}


@app.get("/articles/search/{keyword}")
def search(keyword: str):
    return hub.search(keyword)


@app.post("/articles/import")
def import_md(body: ImportIn):
    return {"id": hub.import_md(body.path, tags=body.tags)}


# ---------------- 发布 / 更新 ----------------

@app.post("/articles/{aid}/publish")
def publish(aid: int, body: PublishIn):
    return hub.publish(aid, body.platforms, body.account, body.draft_only)


@app.post("/articles/{aid}/update")
def update(aid: int, body: UpdateIn):
    return hub.update(aid, body.platforms, body.account)


@app.post("/sync/pending")
def sync_pending():
    return hub.sync_pending()


@app.get("/publications")
def publications(article_id: int = None, platform: str = None):
    return [dict(r) for r in hub.conn.execute(
        "SELECT * FROM publications WHERE (? IS NULL OR article_id=?) AND (? IS NULL OR platform=?)",
        (article_id, article_id, platform, platform)).fetchall()]


# ---------------- 账号 / 平台 ----------------

@app.get("/platforms")
def platforms():
    from core.adapters.base import ADAPTERS
    return [{"id": a.id, "name": a.name, "needs_browser": a.needs_browser}
            for a in ADAPTERS.values()]


@app.get("/accounts")
def accounts():
    return hub.accounts()


@app.get("/accounts/{platform}/check")
def check_account(platform: str, account: str = "default"):
    return {"platform": platform, "logined": hub.check(platform, account)}


class LoginIn(BaseModel):
    account: str = "default"
    timeout: int = 600
    # handoff=弹验证码就暂停交人工（默认）；abort=无人值守时直接放弃
    on_captcha: str = "handoff"


# 登录是长任务（要等人扫码），HTTP 同步等着必超时。放后台线程跑，前端轮询状态。
LOGIN_TASKS = {}
LOGIN_TASK_TTL = 600      # 完成后保留 10 分钟供前端最后拉一次，然后清掉
LOGIN_TASK_MAX = 100      # 上限保护：字典只增不删会慢慢吃内存


def _gc_login_tasks():
    now_ts = time.time()
    dead = [k for k, v in LOGIN_TASKS.items()
            if v.get("status") != "running"
            and now_ts - v.get("finished_at", now_ts) > LOGIN_TASK_TTL]
    for k in dead:
        LOGIN_TASKS.pop(k, None)
    # 超上限时丢最旧的（含 running，极端场景下可接受）
    while len(LOGIN_TASKS) > LOGIN_TASK_MAX:
        LOGIN_TASKS.pop(next(iter(LOGIN_TASKS)), None)


@app.post("/accounts/{platform}/login")
def login(platform: str, body: LoginIn):
    """异步启动登录：立即返回 task_id，前端轮询 /login/status。
    会开一个有头浏览器，去平台登录页，等你扫码；登录态落盘后任务结束。"""
    import threading
    import uuid
    task_id = uuid.uuid4().hex[:10]
    LOGIN_TASKS[task_id] = {
        "task_id": task_id, "platform": platform, "account": body.account,
        "status": "running",
        "message": "浏览器已打开平台登录页，等待扫码/登录…",
    }

    def _run():
        try:
            ok, msg = hub.login(platform, body.account, body.timeout, body.on_captcha)
            LOGIN_TASKS[task_id].update(ok=ok,
                                        status="success" if ok else "failed",
                                        message=msg, finished_at=time.time())
        except Exception as e:
            LOGIN_TASKS[task_id].update(ok=False, status="failed",
                                        message=f"{type(e).__name__}: {e}",
                                        finished_at=time.time())
        _gc_login_tasks()

    threading.Thread(target=_run, daemon=True).start()
    return {"task_id": task_id, "platform": platform, "status": "running"}


@app.get("/accounts/{platform}/login/status")
def login_status(platform: str, task_id: str = None):
    """轮询登录任务状态：running / success / failed。"""
    if task_id and task_id in LOGIN_TASKS:
        return LOGIN_TASKS[task_id]
    for t in reversed(list(LOGIN_TASKS.values())):
        if t["platform"] == platform:
            return t
    return {"platform": platform, "status": "idle", "message": "没有登录任务"}


@app.get("/accounts/{platform}/diagnose")
def diagnose(platform: str):
    """这个平台该怎么接、验证码怎么过——排查用。"""
    return hub.diagnose(platform)


class CaptchaIn(BaseModel):
    account: str = "default"
    wait: int = 180


@app.post("/accounts/{platform}/solve-captcha")
def solve_captcha(platform: str, body: CaptchaIn):
    """打开页面就地处理验证码：先半自动试，不行暂停等人工。"""
    return hub.solve_captcha(platform, body.account, body.wait)


@app.post("/refresh/{platform}")
def refresh(platform: str, limit: int = 50):
    return hub.refresh(platform, limit=limit)


# ---------------- AI 写稿 ----------------

@app.post("/ai/write")
def ai_write(body: AIWriteIn):
    return hub.ai_write(body.topic, body.style, body.words,
                        body.tags_hint, body.publish_to)


@app.post("/articles/{aid}/ai-rewrite")
def ai_rewrite(aid: int, body: AIRewriteIn):
    return hub.ai_rewrite(aid, body.instruction, body.publish_to)


@app.post("/articles/{aid}/ai-polish")
def ai_polish(aid: int):
    return hub.ai_polish(aid)


@app.get("/ai/status")
def ai_status():
    return {"ready": hub.ai_ready()}


@app.get("/jobs")
def jobs(limit: int = 50):
    from core import db
    return [dict(r) for r in db.list_jobs(hub.conn, limit)]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8800)
