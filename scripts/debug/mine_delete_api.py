# -*- coding: utf-8 -*-
"""从管理页 JS bundle 里挖删除 API 端点。"""
import sys, time, re, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(8)

# 收集所有 script src（含当前页 + 动态 chunks）
srcs = page.evaluate("""() => {
    const urls = new Set();
    for (const s of document.querySelectorAll('script[src]')) urls.add(s.src);
    // webpack chunks 记录
    try {
        for (const k in window.webpackChunk) {
            // webpackChunk 是数组，不好直接拿 chunk url，跳过
        }
    } catch(e) {}
    // performance API 拿所有已加载的 js
    for (const r of performance.getEntriesByType('resource')) {
        if (r.name.endsWith('.js') || r.name.includes('.js?')) urls.add(r.name);
    }
    return Array.from(urls);
}""")
print(f"找到 {len(srcs)} 个 JS 资源")

hits = []
for u in srcs:
    if "mp_blog" not in u and "manage" not in u and "chunk" not in u and "admin" not in u:
        # 管理页相关 chunk 才值得抓，但拿不准就全抓——数量有限
        pass
    try:
        txt = page.evaluate("""async (u) => {
            const r = await fetch(u);
            return await r.text();
        }""", u)
        # 找 delete 相关的 API 路径
        for m in set(re.findall(r'["\'](/[^"\']{0,80}(?:delete|Delete|remove|Remove)[^"\']{0,80})["\']', txt)):
            hits.append((u.split("/")[-1][:40], m))
    except Exception:
        continue

print(f"\n=== delete 相关端点 ({len(hits)}) ===")
seen = set()
for src, m in hits:
    key = m
    if key in seen:
        continue
    seen.add(key)
    print(f"  [{src}] {m}")
br.close()
