# -*- coding: utf-8 -*-
"""平台适配器接口。

四个动作，AI 能管的全靠这四个：
    check_auth   登录了吗
    list         账号里有哪些文章（顺带把 edit_url 抓回来）
    publish      发一篇新的，返回 post_id
    update       原地更新已发布的（打开 edit_url 改内容再保存）

设计原则：
  1. edit_url 一律从列表页抓，不靠拼 URL —— 拼错了就是灾难，抓来的才准
  2. 平台专属的 URL / API / 选择器全部集中在各适配器顶部常量区，改平台只改那一块
  3. 任何一步失败都抛 PlatformError，由上层记进 jobs 表，不影响其他平台
"""

import json
import time


class PlatformError(Exception):
    pass


class PlatformAdapter:
    id = ""
    name = ""
    needs_browser = True   # 走标准协议的平台（如博客园 MetaWeblog）设 False，省一个浏览器实例
    login_url = ""
    home_url = ""      # 登录后才能进的页面，用来判断登录态
    list_url = ""      # 内容管理页
    new_url = ""       # 新建文章页

    # ---------------- 子类必须实现的四个动作 ----------------

    def check_auth(self, page) -> bool:
        raise NotImplementedError

    def list_articles(self, page, limit=50):
        """返回 [{'post_id','title','url','edit_url','status','stats':{}}]"""
        raise NotImplementedError

    def publish(self, page, article: dict, options: dict = None):
        """返回 {'post_id','post_url','edit_url','draft_only'}"""
        raise NotImplementedError

    def update(self, page, pub: dict, article: dict) -> bool:
        """原地更新。pub 里带着 post_id / edit_url"""
        raise NotImplementedError

    # ---------------- 通用工具 ----------------

    def api_get(self, page, url):
        """在页面上下文里发 GET，自动带 cookie —— 比直接 requests 省事也更像真人。"""
        js = """async (u) => {
            const r = await fetch(u, {credentials: 'include'});
            return {status: r.status, text: await r.text()};
        }"""
        res = page.evaluate(js, url)
        if res["status"] != 200:
            raise PlatformError(f"GET {url} -> HTTP {res['status']}")
        try:
            return json.loads(res["text"])
        except Exception:
            raise PlatformError(f"响应不是 JSON: {res['text'][:200]}")

    def api_post(self, page, url, payload):
        js = """async ([u, body]) => {
            const r = await fetch(u, {
                method: 'POST',
                credentials: 'include',
                headers: {'content-type': 'application/json'},
                body: JSON.stringify(body)
            });
            return {status: r.status, text: await r.text()};
        }"""
        res = page.evaluate(js, [url, payload])
        try:
            data = json.loads(res["text"])
        except Exception:
            raise PlatformError(f"响应不是 JSON: {res['text'][:200]}")
        if res["status"] != 200 or (isinstance(data, dict) and data.get("err_no") not in (0, None)):
            raise PlatformError(f"POST {url} 失败: {res['text'][:200]}")
        return data

    def set_editor_content(self, page, content, editor_sel=".CodeMirror"):
        """
        往 Markdown 编辑器里塞内容。三级降级，从最快到最稳：
          1. CodeMirror 实例 setValue（秒级，编辑器能感知）
          2. 剪贴板粘贴
          3. 逐字输入（慢，但一定能触发事件）
        """
        # 1) CodeMirror
        try:
            ok = page.evaluate("""([sel, text]) => {
                const el = document.querySelector(sel);
                if (!el) return false;
                const cm = el.CodeMirror || (el.querySelector('.CodeMirror') || {}).CodeMirror;
                if (cm && cm.setValue) { cm.setValue(text); return true; }
                return false;
            }""", [editor_sel, content])
            if ok:
                time.sleep(0.5)
                return "codemirror"
        except Exception:
            pass

        # 2) 剪贴板
        try:
            page.evaluate("(t) => navigator.clipboard.writeText(t)", content)
            page.click(editor_sel, timeout=5000)
            page.keyboard.press("Control+A")
            page.keyboard.press("Control+V")
            time.sleep(0.8)
            return "clipboard"
        except Exception:
            pass

        # 3) 硬输
        page.click(editor_sel, timeout=5000)
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        page.keyboard.insert_text(content)
        return "typing"

    def save_debug(self, page, tag):
        from core.browser import dump_dom
        path = dump_dom(page, tag)
        return str(path)


ADAPTERS = {}


def register(cls):
    ADAPTERS[cls.id] = cls()
    return cls


def get_adapter(platform):
    if platform not in ADAPTERS:
        raise PlatformError(f"不支持的平台: {platform}，已注册: {list(ADAPTERS)}")
    return ADAPTERS[platform]
