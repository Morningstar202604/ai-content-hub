# -*- coding: utf-8 -*-
"""REST API：AI 或你自己的脚本通过这个管整个中台。

启动：  python -m server.api     或     uvicorn server.api:app --port 8800
文档：  http://127.0.0.1:8800/docs
"""

import json
import os
import sys
import time
from ipaddress import ip_address, ip_network
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Literal, Optional

from core.service import Hub
from core import observability as obs

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="AI 内容中台", version="0.2.0")
hub = Hub(headless=True)

# ---------------- 可选 API 鉴权 ----------------
# config.json 里配 "api_token": "一串随机字符串" 即启用：
# 非信任来源的除 /static 与根路径外所有请求，必须带 X-API-Token 头。默认不配 = 不启用（本地用）。
# 信任来源：本机回环 / testclient / 信任网段（可经环境变量 TRUSTED_NETS 追加 CIDR）。
def _api_token():
    try:
        return (json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
                or {}).get("api_token") or ""
    except Exception:
        return ""


def _trusted_sources():
    """本机回环 + 测试客户端 + 配置的信任网段（CIDR）。"""
    nets = ["127.0.0.0/8", "::1/128"]
    extra = os.environ.get("TRUSTED_NETS", "").strip()
    if extra:
        nets += [n.strip() for n in extra.split(",") if n.strip()]
    return nets


def _client_ip(request):
    """反代感知取真实客户端 IP：优先 X-Forwarded-For 首个，回退到直连 host。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        first = fwd.split(",")[0].strip()
        try:
            return ip_address(first)
        except ValueError:
            pass
    host = request.client.host if request.client else ""
    if host:
        try:
            return ip_address(host)
        except ValueError:
            pass
    return None


def _is_trusted(request):
    ip = _client_ip(request)
    if ip is None:
        return False
    for net in _trusted_sources():
        try:
            if ip in ip_network(net, strict=False):
                return True
        except Exception:
            continue
    return False


@app.middleware("http")
async def _auth(request, call_next):
    token = _api_token()
    if token and not _is_trusted(request) \
            and request.headers.get("X-API-Token") != token \
            and not request.url.path.startswith("/static"):
        return JSONResponse({"detail": "无效的 API Token"}, status_code=401)
    return await call_next(request)


# ---------------- 可观测性：结构化 access log + 指标 ----------------
# 每个 API 请求落一条 JSON 行到 data/observability/events.log，
# 带 method/path/status/duration/client_ip，排障时直接 grep 链路。
# /static 与 /metrics 自身不记录（避免指标端点把日志刷爆）。

_LOG_SKIP = ("/static/", "/metrics", "/health", "/docs", "/openapi.json", "/redoc")


@app.middleware("http")
async def _access_log(request, call_next):
    t0 = time.time()
    resp = await call_next(request)
    dur = round(time.time() - t0, 3)
    path = request.url.path
    if not any(path.startswith(s) for s in _LOG_SKIP):
        status = getattr(resp, "status_code", 0)
        ok = 200 <= status < 400
        obs.METRICS.incr(f"api.{ 'ok' if ok else 'fail' }")
        obs.METRICS.observe("api.dur", dur)
        obs.METRICS.incr(f"api.{request.method.lower()}.hits")
        obs.emit("api.access",
                 method=request.method, path=path, status=status,
                 duration=dur,
                 client_ip=(request.client.host if request.client else ""))
    return resp

# ---------------- CORS（默认仅同源；跨域部署时用环境变量 CORS_ORIGINS 白名单） ----------------
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

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
    live: bool = False      # true=附带实时预览页（异步端点专用）


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


# 体检 B5 修复（QA 标质力 2026-09-21）：发布是 70s+ 的长任务，同步 HTTP 必超时。
# 仿 LOGIN_TASKS 模式加异步任务：立即返回 task_id，轮询取结果。原同步端点保留
# （Web 前端零改动）；AI/无人值守调用走这个异步口。live=True 时附带实时预览页。
PUBLISH_TASKS = {}
PUBLISH_TASK_TTL = 1800     # 完成后保留 30 分钟（含预览页观看窗口）
PUBLISH_TASK_MAX = 50


def _gc_publish_tasks():
    now_ts = time.time()
    dead = [k for k, v in PUBLISH_TASKS.items()
            if v.get("status") != "running"
            and now_ts - v.get("finished_at", now_ts) > PUBLISH_TASK_TTL]
    for k in dead:
        mon = PUBLISH_TASKS[k].pop("_monitor", None)
        if mon:
            try:
                mon.stop()
            except Exception:
                pass
        PUBLISH_TASKS.pop(k, None)
    while len(PUBLISH_TASKS) > PUBLISH_TASK_MAX:
        k = next(iter(PUBLISH_TASKS))
        mon = PUBLISH_TASKS[k].pop("_monitor", None)
        if mon:
            try:
                mon.stop()
            except Exception:
                pass
        PUBLISH_TASKS.pop(k, None)


@app.post("/articles/{aid}/publish/async")
def publish_async(aid: int, body: PublishIn):
    """异步发布：立即返回 task_id，轮询 GET /publish/tasks/{task_id}。
    live=true 时同线程挂 LiveMonitor（CDP 截屏流），返回的 preview_url
    可直接在应用内置浏览器面板打开围观整个发布过程。"""
    import threading
    import uuid
    task_id = uuid.uuid4().hex[:10]
    PUBLISH_TASKS[task_id] = {
        "task_id": task_id, "article_id": aid, "platforms": body.platforms,
        "account": body.account, "draft_only": body.draft_only,
        "status": "running", "message": "排队中…", "result": None,
    }

    def _run():
        mon = None
        try:
            hook = None
            if body.live:
                from core.liveview import LiveMonitor
                mon = LiveMonitor(port=0, platform="+".join(body.platforms))
                mon.start()
                PUBLISH_TASKS[task_id]["preview_url"] = mon.url()
                PUBLISH_TASKS[task_id]["_monitor"] = mon

                def hook(page):
                    # CDP 截屏由浏览器推帧，规避 greenlet 线程限制
                    mon.attach_cdp(page)
                    mon.log(f"发布任务 {task_id} 开始：{body.platforms}")

            result = hub.publish(aid, body.platforms, body.account,
                                 body.draft_only, page_hook=hook)
            PUBLISH_TASKS[task_id].update(status="success", result=result,
                                          finished_at=time.time(),
                                          message="发布完成")
            if mon:
                mon.log("发布任务完成 ✓")
        except Exception as e:
            PUBLISH_TASKS[task_id].update(
                status="failed", message=f"{type(e).__name__}: {e}",
                finished_at=time.time())
            if mon:
                mon.log(f"发布任务失败 ✗ {type(e).__name__}: {str(e)[:120]}")
        _gc_publish_tasks()

    threading.Thread(target=_run, daemon=True).start()
    return {"task_id": task_id, "status": "running",
            "poll": f"/publish/tasks/{task_id}"}


@app.get("/publish/tasks/{task_id}")
def publish_task_status(task_id: str):
    """轮询异步发布任务：running / success / failed（含 result 与 preview_url）。"""
    task = PUBLISH_TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "status": "unknown",
                "message": "任务不存在或已过期（保留 30 分钟）"}
    return {k: v for k, v in task.items() if not k.startswith("_")}


# legacy 回退路径（strangler 第二刀/M5）：主路径为 POST /articles/{aid}/update/workflow；
# 语义冻结见 docs/design/m5-api.md §7-C；防双发纪律：同一文章同一平台只走一条路径
@app.post("/articles/{aid}/update")
def update(aid: int, body: UpdateIn):
    return hub.update(aid, body.platforms, body.account)


# legacy 回退路径（strangler 第二刀/M5）：主路径为 POST /sync/pending/workflow（一文一 run）
@app.post("/sync/pending")
def sync_pending():
    return hub.sync_pending()


@app.get("/pending-human")
def pending_human():
    """需要人工处理的发布实例（如掘金草稿等人点"确定并发布"）。
    前端轮询这个端点做角标提醒；点"去处理"直接打开草稿编辑页。"""
    rows = hub.conn.execute(
        """SELECT p.article_id, a.title, p.platform, p.account, p.edit_url,
                  p.post_id, p.updated_at
           FROM publications p LEFT JOIN articles a ON a.id = p.article_id
           WHERE p.status = 'pending_human'
           ORDER BY p.updated_at DESC""").fetchall()
    return [dict(r) for r in rows]


@app.get("/publications")
def publications(article_id: int = None, platform: str = None):
    # 动态参数化：占位符与实参一一对应，避免把「过滤为 None 则不过滤」压进隐式 SQL
    # 联查文章标题（管理视图直接显示标题，不用拿 ID 再查一遍）
    sql = ("SELECT p.*, a.title FROM publications p "
           "LEFT JOIN articles a ON a.id = p.article_id WHERE 1=1")
    args = []
    if article_id is not None:
        sql += " AND p.article_id=?"
        args.append(article_id)
    if platform is not None:
        sql += " AND p.platform=?"
        args.append(platform)
    sql += " ORDER BY p.updated_at DESC"
    return [dict(r) for r in hub.conn.execute(sql, args).fetchall()]


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


class AssistIn(BaseModel):
    url: str
    timeout: int = 900


ASSIST_TASKS = {}
ASSIST_TASK_MAX = 20


@app.post("/accounts/{platform}/assist")
def assist_open(platform: str, body: AssistIn):
    """带登录态的内置有头浏览器打开平台页（人工步骤接管，不必去平台站点重登录）。"""
    import threading as _th, uuid as _uuid
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(422, "url 必须是 http(s) 地址")
    task_id = _uuid.uuid4().hex[:10]
    if len(ASSIST_TASKS) > ASSIST_TASK_MAX:
        for k in list(ASSIST_TASKS)[: len(ASSIST_TASKS) - ASSIST_TASK_MAX]:
            ASSIST_TASKS.pop(k, None)
    ASSIST_TASKS[task_id] = {"task_id": task_id, "platform": platform,
                             "url": body.url, "status": "running",
                             "message": "内置浏览器已打开平台页（带登录态），等待人工操作…"}
    def _run():
        try:
            r = hub.assist_open(platform, body.url, body.timeout)
            ASSIST_TASKS[task_id].update(status="done", message=r.get("msg", ""),
                                         finished_at=time.time())
        except Exception as e:   # aqg: top-level boundary（assist 任务失败落终态）
            ASSIST_TASKS[task_id].update(status="failed",
                                         message=f"{type(e).__name__}: {str(e)[:200]}",
                                         finished_at=time.time())
    _th.Thread(target=_run, daemon=True).start()
    return {"task_id": task_id, "status": "running",
            "poll": f"/accounts/{platform}/assist/status?task_id={task_id}"}


@app.get("/accounts/{platform}/assist/status")
def assist_status(platform: str, task_id: str = None):
    if task_id and task_id in ASSIST_TASKS:
        return ASSIST_TASKS[task_id]
    for t in reversed(list(ASSIST_TASKS.values())):
        if t["platform"] == platform:
            return t
    return {"platform": platform, "status": "idle", "message": "没有 assist 任务"}


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


@app.get("/ai/gate")
def ai_gate():
    """AIGC 合规门禁状态：开关、审查模型、高危词数、最近拒绝。"""
    from core import gate as g
    snap = {"enabled": g.is_enabled(),
            "review_model": g._cfg("REVIEW_MODEL", "").strip() or "(未配置，走本地 heuristic)",
            "dangerous_terms": len(g.DANGEROUS_PATTERNS),
            "human_review_gate": "AI 源内容禁止直接 publish，须 draft_only + 人工确认"}
    # 最近 10 条被门禁拒绝的发布（jobs 里 failed 且 message 含 门禁/高危/人工）
    try:
        rows = hub.conn.execute(
            "SELECT * FROM jobs WHERE type='publish' AND status='failed' "
            "ORDER BY id DESC LIMIT 50").fetchall()
        denied = [dict(r) for r in rows if any(
            k in (r["message"] or "") for k in ("门禁", "高危", "人工确认", "合规"))]
        snap["recent_denied"] = denied[:10]
    except Exception:
        snap["recent_denied"] = []
    return snap


@app.get("/jobs")
def jobs(limit: int = 50):
    from core import db
    return [dict(r) for r in db.list_jobs(hub.conn, limit)]


# ---------------- 可观测性端点 ----------------

@app.get("/metrics")
def metrics():
    """实时指标快照：计数器 + 耗时直方图 + 事件计数。

    重启归零；长期趋势看 jobs 表 + events.log（grep trace_id 串联链路）。
    """
    snap = obs.METRICS.snapshot()
    snap["events_log"] = str(obs.EVENT_LOG)
    snap["trace_hint"] = "发布/更新链路 grep 'trace' + trace_id 于 events.log"
    return snap


@app.get("/health")
def health():
    """存活探测：DB 可读 + 事件日志可写 + AI 是否就绪。供反代/监控探活。"""
    from core import db
    db_ok = False
    try:
        db_ok = hub.conn.execute("SELECT 1").fetchone()[0] == 1
    except Exception:
        pass
    log_ok = Path(obs.EVENT_LOG.parent).exists()
    return {"ok": db_ok and log_ok, "db": db_ok, "events_log": log_ok,
            "ai_ready": hub.ai_ready(), "ts": time.time()}


# ---------------- 工作流运行（LangGraph 引擎，ADR-001/003） ----------------
# 绞杀者增量：以下端点为增量新增，legacy /publish 端点原样保留可随时回退。
# config.json 设 "workflow": {"enabled": false} 可整体禁用新引擎。

_RUNNER = None


def _workflow_runner():
    global _RUNNER
    if _RUNNER is None:
        from workflows.runner import WorkflowRunner
        _RUNNER = WorkflowRunner(hub)
    return _RUNNER


def _workflow_enabled():
    try:
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        return bool((cfg.get("workflow") or {}).get("enabled", True))
    except Exception:
        return True


class WorkflowPublishIn(BaseModel):
    platforms: List[str]
    account: str = "default"
    draft_only: bool = False
    dry_run: bool = False     # true=预演：不触真实平台，合成结果（冒烟/演练用）


class ResumeIn(BaseModel):
    approved: bool = True
    note: str = ""


class WorkflowUpdateIn(BaseModel):
    """M5 原地更新工作流入参（m5-api.md §2；无 draft_only——update 无草稿概念）"""
    platforms: Optional[List[str]] = None   # null/缺省/[] 三者等价 = 全部可更新实例（B1）
    account: str = "default"
    dry_run: bool = False


class WorkflowSyncIn(BaseModel):
    """M5 同步扇出入参（m5-api.md §3；body 可整体省略）"""
    account: str = "default"
    dry_run: bool = False


@app.post("/articles/{aid}/publish/workflow")
def publish_workflow(aid: int, body: WorkflowPublishIn):
    """Agent 驱动的工作流发布：立即返回 run_id，轮询 GET /runs/{run_id}。
    挂起（waiting_human）时 result.human_task 带人工处理载荷，POST /runs/{id}/resume 恢复。"""
    if not _workflow_enabled():
        raise HTTPException(409, "工作流引擎已通过 config workflow.enabled=false 禁用")
    try:
        return _workflow_runner().start(aid, body.platforms, body.account,
                                        body.draft_only, body.dry_run)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/articles/{aid}/update/workflow")
def update_workflow(aid: int, body: WorkflowUpdateIn):
    """原地更新工作流（kind=update，绞杀者第二刀）：立即返回 run_id，轮询 GET /runs/{run_id}。
    与 legacy /update 并存（legacy 冻结保留，m5-api.md §7-C）。
    错误映射（D-A，勿照抄 publish 的一律 404）：ValueError 按文案分流——
    含"不存在"→404；含"没有已发布实例"→422；409 引擎禁用先于一切预检（B5）。"""
    if not _workflow_enabled():
        raise HTTPException(409, "工作流引擎已通过 config workflow.enabled=false 禁用")
    try:
        return _workflow_runner().start(aid, body.platforms, body.account,
                                        kind='update', dry_run=body.dry_run)
    except ValueError as e:
        msg = str(e)
        if "不存在" in msg:
            raise HTTPException(404, msg)
        raise HTTPException(422, msg)


@app.post("/sync/pending/workflow")
def sync_pending_workflow(body: WorkflowSyncIn = WorkflowSyncIn()):
    """同步扇出（ADR-008，一文一 run）：发现 pending → 按文章分组 → 逐篇启动 update run。
    单篇启动失败进 failed[] 不升级全局错误（D-D/B4）；count=0 非错误（B7）。"""
    if not _workflow_enabled():
        raise HTTPException(409, "工作流引擎已通过 config workflow.enabled=false 禁用")
    from core import db as hub_db
    rows = hub_db.get_pending_updates(hub.conn)
    groups = {}
    for r in rows:
        groups.setdefault(r["article_id"], {"title": r["title"], "platforms": []})
        groups[r["article_id"]]["platforms"].append(r["platform"])
    runs, failed = [], []
    for aid, info in groups.items():
        try:
            r = _workflow_runner().start(aid, sorted(set(info["platforms"])),
                                         body.account, kind='update',
                                         dry_run=body.dry_run)
            runs.append({"article_id": aid, "title": info["title"],
                         "run_id": r["run_id"]})
        except ValueError as e:
            failed.append({"article_id": aid, "title": info["title"],
                           "reason": str(e)})
    return {"count": len(runs), "runs": runs, "failed": failed}


@app.get("/runs")
def runs_list(limit: int = 50,
              kind: Optional[Literal["publish", "update"]] = None,
              article_id: Optional[int] = None):
    """运行列表（向后兼容增强）：可选 kind/article_id 过滤，缺省返回全部 kind；
    响应项新增 kind 字段（存量行 'publish'，m5-api.md §4.1）。"""
    return _workflow_runner().list(limit, kind=kind, article_id=article_id)


@app.get("/runs/{run_id}")
def runs_detail(run_id: str):
    r = _workflow_runner().get(run_id)
    if not r:
        raise HTTPException(404, "run 不存在")
    return r


@app.post("/runs/{run_id}/resume")
def runs_resume(run_id: str, body: ResumeIn):
    """恢复挂起的 run：approved=true 表示人已在平台侧完成最后一步（如掘金点发布）。"""
    try:
        return _workflow_runner().resume(run_id, body.approved, body.note)
    except ValueError as e:
        raise HTTPException(409, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8800)
