# -*- coding: utf-8 -*-
"""精读 bundle 中 publish 调用的上下文，找完整 payload 字段。"""
import sys, time, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser

br = BuiltinBrowser("juejin", "default", headless=True)
page = br.start().new_page()

loaded_js = []


def on_resp(resp):
    u = resp.url
    if "lf-web-assets.juejin.cn" not in u and "unpkg.byted-static.com" not in u:
        return
    try:
        body = resp.text()
        loaded_js.append((u, body))
    except Exception:
        pass


page.on("response", on_resp)
page.goto("https://juejin.cn/editor/drafts/new", timeout=60000,
          wait_until="domcontentloaded")
time.sleep(15)

# 找 app.js 里的 publish 调用上下文
for u, b in loaded_js:
    if "app." not in u:
        continue
    # 找 article/publish 路径定义
    m1 = re.search(r'article/publish.{0,200}', b)
    if m1:
        print("=== article/publish 路径定义上下文 ===")
        print(m1.group(0)[:300])
    # 找 s["e"] 这种引用
    m1b = re.search(r'"e"\)\(.{0,300}', b)
    if m1b:
        print("\n=== s[\"e\"] 调用 ===")
        print(m1b.group(0)[:300])
    # 找 maskCount / realCount 计算
    m1c = re.search(r'maskCount.{0,500}', b)
    if m1c:
        print("\n=== maskCount 上下文 ===")
        print(m1c.group(0)[:500])
    # 找 level 的获取
    m1d = re.search(r'\$store\.state\.auth\.user.{0,200}', b)
    if m1d:
        print("\n=== auth.user 获取 ===")
        print(m1d.group(0)[:300])
    # 找 publishDraft / publish 调用的完整上下文
    m = re.search(r'f\.addMark\("publishDraft".{0,2000}', b, re.S)
    if m:
        print("=== publishDraft 上下文 ===")
        print(m.group(0)[:2000])
    # 找 s["e"] 在哪定义（即 publishDraft 函数本身）
    # 通常这种 minified 代码： s["e"] 是某个 import 模块
    # 搜 "publishDraft" 字符串
    m2 = re.search(r'publishDraft.{0,500}', b)
    if m2:
        print("\n=== publishDraft 调用点 ===")
        print(m2.group(0)[:600])
    # 找 encrypted_word_count
    m3 = re.search(r'encrypted_word_count.{0,300}', b)
    if m3:
        print("\n=== encrypted_word_count 上下文 ===")
        print(m3.group(0)[:400])
    # 找 level 的用法（auth.user.level）
    m4 = re.search(r'auth\.user\.level.{0,200}', b)
    if m4:
        print("\n=== auth.user.level ===")
        print(m4.group(0)[:300])
    # 找所有 publish 相关的 API 路径
    m5 = re.findall(r'content_api/v1/article[a-z_/]*|article_draft/[a-z_]+', b)
    print("\n=== article API 路径 ===")
    from collections import Counter
    for path, cnt in Counter(m5).most_common(30):
        print(f"  {cnt:3d}  {path}")

br.close()
