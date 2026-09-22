# -*- coding: utf-8 -*-
"""端到端验收：真实发布 + CDP 实时预览 + 记账对账（体检修复全量验证）。"""
import sys, time, json, threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.service import Hub
from core.liveview import LiveMonitor

hub = Hub(headless=True)

# 1) 建文章（代码块补语言标注以过合规门禁）
import re
_md = Path("data/test_article.md").read_text(encoding="utf-8")
_parts = _md.split("\n")
in_block = False
for i, line in enumerate(_parts):
    s = line.strip()
    if not s.startswith("```"):
        continue
    if not in_block:
        # 开栏：裸栏补 text 标注（合规门禁要求代码块标语言）
        if s == "```":
            _parts[i] = "```text"
        in_block = True
    else:
        in_block = False     # 闭栏
_md = "\n".join(_parts)
aid = hub.conn.execute(
    "INSERT INTO articles (title, content_md, summary, status, source, created_at, updated_at)"
    " VALUES (?,?,?,?,?,?,?)",
    ("工作流体检验收：全链路发布完整性验证", _md,
     "全栈战队体检后的端到端验收文章：真实发布 + 记账对账 + 实时预览。",
     "draft", "human", __import__("core.db", fromlist=["now"]).now(),
     __import__("core.db", fromlist=["now"]).now())
).lastrowid
hub.conn.commit()
print(f"文章已建 id={aid}")

# 2) 挂实时预览（port=0 自动分配）
mon = LiveMonitor(port=0, platform="CSDN")
mon.start()
frames = {"n": 0}
_orig_lock = mon._lock

def hook(page):
    ok = mon.attach_cdp(page)
    print(f"CDP 截屏挂载: {ok}  预览页: {mon.url()}")

# 3) 真实发布（走体检修复后的完整链路）
t0 = time.time()
result = hub.publish(aid, ["csdn"], draft_only=False, page_hook=hook)
print(f"\n发布耗时 {time.time()-t0:.0f}s")
print("结果:", json.dumps(result, ensure_ascii=False, indent=1))

# 4) 记账对账
pub = hub.conn.execute(
    "SELECT * FROM publications WHERE article_id=? AND platform='csdn'", (aid,)).fetchone()
jobs = hub.conn.execute(
    "SELECT * FROM jobs WHERE article_id=? AND platform='csdn' ORDER BY id DESC LIMIT 1",
    (aid,)).fetchone()
art = hub.conn.execute("SELECT status FROM articles WHERE id=?", (aid,)).fetchone()
print(f"\n=== 记账对账 ===")
print(f"publications: status={pub['status'] if pub else '无'} post_id={pub['post_id'] if pub else '-'}")
print(f"job: status={jobs['status'] if jobs else '无'} message={jobs['message'] if jobs else '-'}")
print(f"article: status={art['status'] if art else '-'}")

# 5) 预览帧流量统计（CDP 截屏是否真出帧）
time.sleep(8)
with mon._lock:
    has_frame = bool(mon._shot_bytes)
print(f"\n实时预览帧: {'✓ 有画面' if has_frame else '✗ 无帧'}  预览地址: {mon.url()}")

# 6) 断言
ok_pub = bool(result and isinstance(result, list) and result
              and result[0].get("ok") and result[0].get("post_id"))
ok_db = bool(pub and pub["status"] == "ok" and pub["post_id"])
ok_job = bool(jobs and jobs["status"] == "ok")
ok_art = bool(art and art["status"] == "published")
print(f"\n=== 验收断言 ===")
print(f"发布结果含 post_id: {ok_pub}")
print(f"publications 记账 ok: {ok_db}")
print(f"job 记账 ok: {ok_job}")
print(f"article 状态 published: {ok_art}")
print(f"总验收: {'✅ 全部通过' if all([ok_pub, ok_db, ok_job, ok_art]) else '❌ 有失败项'}")

# 保持预览 3 分钟供观看
print("\n预览保持 180s…")
time.sleep(180)
mon.stop()
