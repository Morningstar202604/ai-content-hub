# -*- coding: utf-8 -*-
"""数据层：SQLite 单文件，AI 管的就是这几张表。

四张核心表：
  accounts     平台账号（一个平台一个内置浏览器 profile）
  articles     文章主库（唯一真源，AI 写/改的都是它）
  publications 发布实例（一篇文章 × 一个平台 = 一条，存 post_id / edit_url，原地更新靠它）
  jobs         任务流水（谁在什么时候发了什么，失败原因可查）
"""

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "hub.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    platform     TEXT NOT NULL,
    name         TEXT NOT NULL DEFAULT 'default',
    profile_dir  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'unknown',   -- unknown/logined/offline
    last_check   REAL,
    UNIQUE(platform, name)
);

CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    content_md  TEXT NOT NULL DEFAULT '',
    summary     TEXT DEFAULT '',
    tags        TEXT DEFAULT '',        -- 逗号分隔
    cover       TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'draft',  -- draft/review/published/archived
    source      TEXT DEFAULT 'human',   -- human/ai/import
    ai_model    TEXT DEFAULT '',
    origin_url  TEXT DEFAULT '',        -- 导入来源
    ext         TEXT DEFAULT '{}',      -- JSON 扩展字段
    created_at  REAL,
    updated_at  REAL
);

CREATE TABLE IF NOT EXISTS publications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER NOT NULL,
    platform    TEXT NOT NULL,
    account     TEXT NOT NULL DEFAULT 'default',
    post_id     TEXT DEFAULT '',        -- 平台文章 ID，原地更新的钥匙
    post_url    TEXT DEFAULT '',
    edit_url    TEXT DEFAULT '',        -- 编辑页地址，从列表页抓的，不猜
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending/ok/failed
    draft_only  INTEGER DEFAULT 1,      -- 是否只到草稿
    stats       TEXT DEFAULT '{}',      -- 阅读/点赞等 JSON
    last_error  TEXT DEFAULT '',
    published_at REAL,
    updated_at  REAL,
    UNIQUE(article_id, platform, account)
);

CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,          -- publish/update/sync/import
    article_id  INTEGER,
    platform    TEXT,
    status      TEXT NOT NULL DEFAULT 'running',  -- running/ok/failed
    message     TEXT DEFAULT '',
    created_at  REAL,
    finished_at REAL
);

CREATE INDEX IF NOT EXISTS idx_pub_article ON publications(article_id);
CREATE INDEX IF NOT EXISTS idx_pub_platform ON publications(platform);
"""


def connect(db_path=None):
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False：FastAPI 把同步端点丢进线程池执行，
    # 连接却建在主线程，不开这个开关会报 "created in a thread can only be used in that same thread"
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL：读写不互斥；busy_timeout：多线程同时写时等待而不是立刻报 database is locked
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    prune_jobs(conn, keep=500)
    return conn


def prune_jobs(conn, keep=500):
    """jobs 表只留最近 keep 条流水，防止无限膨胀（每次启动清一次）。"""
    try:
        conn.execute("""DELETE FROM jobs WHERE id NOT IN
                        (SELECT id FROM jobs ORDER BY id DESC LIMIT ?)""", (keep,))
        conn.commit()
    except Exception:
        pass


def now():
    return time.time()


# --------------------------- articles ---------------------------

def create_article(conn, title, content_md="", **kw):
    cur = conn.execute(
        """INSERT INTO articles (title, content_md, summary, tags, cover, status,
           source, ai_model, origin_url, ext, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (title, content_md, kw.get("summary", ""), kw.get("tags", ""),
         kw.get("cover", ""), kw.get("status", "draft"), kw.get("source", "human"),
         kw.get("ai_model", ""), kw.get("origin_url", ""), kw.get("ext", "{}"),
         now(), now()),
    )
    conn.commit()
    return cur.lastrowid


def update_article(conn, article_id, **kw):
    kw = {k: v for k, v in kw.items() if v is not None}
    if not kw:
        return False
    kw["updated_at"] = now()
    sets = ", ".join(f"{k}=?" for k in kw)
    conn.execute(f"UPDATE articles SET {sets} WHERE id=?", (*kw.values(), article_id))
    conn.commit()
    # 内容变了，已发布的实例全部标记待更新
    if "content_md" in kw or "title" in kw:
        conn.execute(
            """UPDATE publications SET status='pending', last_error='内容已变更待同步'
               WHERE article_id=? AND status='ok'""", (article_id,))
        conn.commit()
    return True


def get_article(conn, article_id):
    return conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()


def list_articles(conn, status=None, limit=100, offset=0):
    sql = "SELECT * FROM articles"
    args = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    return conn.execute(sql, args).fetchall()


def search_articles(conn, keyword):
    return conn.execute(
        "SELECT * FROM articles WHERE title LIKE ? OR content_md LIKE ? ORDER BY updated_at DESC LIMIT 50",
        (f"%{keyword}%", f"%{keyword}%")).fetchall()


# ------------------------- publications -------------------------

def upsert_publication(conn, article_id, platform, account="default", **kw):
    row = conn.execute(
        "SELECT * FROM publications WHERE article_id=? AND platform=? AND account=?",
        (article_id, platform, account)).fetchone()
    if row:
        kw = {k: v for k, v in kw.items() if v is not None}
        if kw:
            kw["updated_at"] = now()
            sets = ", ".join(f"{k}=?" for k in kw)
            conn.execute(f"UPDATE publications SET {sets} WHERE id=?",
                         (*kw.values(), row["id"]))
            conn.commit()
        return row["id"]
    cur = conn.execute(
        """INSERT INTO publications (article_id, platform, account, post_id, post_url,
           edit_url, status, draft_only, stats, last_error, published_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (article_id, platform, account, kw.get("post_id", ""), kw.get("post_url", ""),
         kw.get("edit_url", ""), kw.get("status", "pending"),
         kw.get("draft_only", 1), kw.get("stats", "{}"), kw.get("last_error", ""),
         kw.get("published_at"), now()))
    conn.commit()
    return cur.lastrowid


def get_publications(conn, article_id=None, platform=None, status=None):
    sql = "SELECT * FROM publications WHERE 1=1"
    args = []
    if article_id:
        sql += " AND article_id=?"; args.append(article_id)
    if platform:
        sql += " AND platform=?"; args.append(platform)
    if status:
        sql += " AND status=?"; args.append(status)
    return conn.execute(sql + " ORDER BY updated_at DESC", args).fetchall()


def get_pending_updates(conn):
    """内容改过但还没同步到平台的实例——原地更新的待办清单"""
    return conn.execute(
        """SELECT p.*, a.title, a.content_md FROM publications p
           JOIN articles a ON a.id = p.article_id
           WHERE p.status='pending' AND p.post_id != '' """).fetchall()


# ---------------------------- jobs -----------------------------

def add_job(conn, type_, article_id=None, platform=None):
    cur = conn.execute(
        "INSERT INTO jobs (type, article_id, platform, status, created_at) VALUES (?,?,?,?,?)",
        (type_, article_id, platform, "running", now()))
    conn.commit()
    return cur.lastrowid


def finish_job(conn, job_id, ok, message=""):
    conn.execute("UPDATE jobs SET status=?, message=?, finished_at=? WHERE id=?",
                 ("ok" if ok else "failed", message, now(), job_id))
    conn.commit()


def list_jobs(conn, limit=50):
    return conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


# --------------------------- accounts ---------------------------

def upsert_account(conn, platform, name, profile_dir, status="unknown"):
    conn.execute(
        """INSERT INTO accounts (platform, name, profile_dir, status, last_check)
           VALUES (?,?,?,?,?)
           ON CONFLICT(platform, name) DO UPDATE SET profile_dir=?, status=?, last_check=?""",
        (platform, name, profile_dir, status, now(), profile_dir, status, now()))
    conn.commit()


def list_accounts(conn):
    return conn.execute("SELECT * FROM accounts ORDER BY platform").fetchall()
