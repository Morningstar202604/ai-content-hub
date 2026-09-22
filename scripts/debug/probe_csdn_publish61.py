# -*- coding: utf-8 -*-
"""CSDN 发布决定性探针：完整模拟真人操作
1. 展开目录 dropdown（点 .tag__btn-tag），真实点击一个 label，看 hidden categories 是否写入
2. 填摘要、选标签
3. 监听 publish API 请求+响应，点发布
4. 若仍 0 请求，dump 弹窗当前校验错误文本
"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
from core.adapters.csdn import CSDNAdapter

ad = CSDNAdapter()
br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
assert ad.check_auth(page), "CSDN 未登录"
print("登录 OK")

page.goto(ad.new_url, timeout=60000, wait_until="domcontentloaded")
try:
    page.wait_for_selector("pre.editor__inner[contenteditable=true], .CodeMirror", timeout=30000)
except Exception:
    pass
time.sleep(3)
content_md = Path("data/test_article.md").read_text(encoding="utf-8")
page.evaluate("""(t) => {
    const input = document.querySelector('.article-bar__title--input');
    if (input) { const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      s.call(input, t); input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true})); }
}""", "【CSDN 决定 61】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)

# 开弹窗
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(8)

# ===== Step 1: 展开目录 dropdown，真实点击 label =====
def hidden_cat():
    return page.evaluate("() => { const c = document.querySelector('.tag__box input[type=hidden][name=categories]'); return c ? c.value : null; }")

print(f"\n[1] 展开前 hidden categories = {hidden_cat()!r}")
# 点 .tag__btn-tag 展开
try:
    page.locator('.tag__btn-tag').first.click(timeout=5000)
    time.sleep(3)
    print("    .tag__btn-tag 点击 OK")
except Exception as e:
    print(f"    .tag__btn-tag 点击失败: {e}")

# 现在 .tag__options-content 应该可见
vis = page.evaluate("() => { const c = document.querySelector('.tag__options-content'); return c ? window.getComputedStyle(c).display : 'none'; }")
print(f"    .tag__options-content display = {vis}")

# 真实点击 label（后端与架构设计）
target = "后端与架构设计"
before = hidden_cat()
try:
    lbl = page.locator(f"label.tag__option-label:has(input[value='{target}'])").first
    # 用 dispatchEvent fallback 前先试 native click
    try:
        lbl.click(timeout=4000)
        time.sleep(1)
        print(f"    label native click OK")
    except Exception as e:
        print(f"    label native click 超时，改用 dispatchEvent: {e}")
        page.evaluate("""(val) => {
            const inps = document.querySelectorAll('input.tag__option-chk');
            for (const c of inps) { if (c.value === val) {
                const lbl = c.closest('label');
                if (lbl) lbl.click(); else c.click();
            } }
        }""", target)
        time.sleep(1)
except Exception as e:
    print(f"    label 点击整体失败: {e}")
after = hidden_cat()
print(f"    点击后 hidden categories = {after!r}  (变化: {before != after})")

# 校验状态
chk = page.evaluate("() => { const c = document.querySelector('input.tag__option-chk[value=后端与架构设计]'); return c ? c.checked : null; }")
print(f"    checkbox checked = {chk}")

# ===== Step 2: 填摘要 =====
try:
    summary = page.locator('.publish-article-modal__body textarea, .modal__content textarea, textarea.el-textarea__inner').first
    summary.fill("Python 协程原理与实战：从 asyncio 到生产架构")
    print("\n[2] 摘要已填")
except Exception as e:
    print(f"\n[2] 摘要填写失败: {e}")
time.sleep(1)

# ===== Step 3: 选标签（可选） =====
try:
    ad._select_tag(page, "Python")
    print("[3] 标签已选")
except Exception as e:
    print(f"[3] 标签选择跳过: {e}")
time.sleep(1)

# ===== Step 4: 监听 publish API 请求+响应，点发布 =====
captured = []
def on_resp(resp):
    try:
        u = resp.url
        if "csdn" not in u:
            return
        if resp.request.method in ("POST", "PUT"):
            body = None
            try:
                body = resp.request.post_data
            except Exception:
                pass
            txt = None
            try:
                txt = resp.text()[:600]
            except Exception:
                txt = "(no body)"
            captured.append({"method": resp.request.method, "url": u, "status": resp.status,
                             "body": (body or "")[:400], "resp": txt})
    except Exception:
        pass
page.on("response", on_resp)

print("\n[4] 点发布文章（红色按钮）")
try:
    pub = page.locator('button.btn-b-red.ml16').first
    pub.click(timeout=6000)
    print("    pub click OK")
except Exception as e:
    print(f"    pub click 失败: {e}")
    try:
        page.locator("text=发布文章").last.click(timeout=4000)
        print("    text=发布文章 fallback OK")
    except Exception as e2:
        print(f"    全部点击失败: {e2}")
time.sleep(10)

print(f"\n--- 捕获 {len(captured)} 个 POST/PUT 响应 ---")
for c in captured:
    print(f"\n  [{c['status']}] {c['method']} {c['url']}")
    if c['body']:
        print(f"    请求 body: {c['body'][:300]}")
    print(f"    响应: {c['resp']}")

# URL 变化
print(f"\n当前 URL: {page.url}")
aid = ""
if "articleId=" in page.url:
    aid = page.url.split("articleId=")[-1].split("&")[0]
print(f"解析 articleId = {aid!r}")

# ===== Step 5: 若 0 请求，dump 弹窗校验文本 =====
if not any("commit" in c["url"] or "publish" in c["url"] or "articleDetail" in c["url"] for c in captured):
    print("\n[5] 无 publish 请求，dump 弹窗当前校验提示文本")
    txt = page.evaluate("""() => {
        const modal = document.querySelector('.publish-article-modal, [class*=modal]');
        if (!modal) return 'no modal';
        // 收集所有带错误提示样式的文本
        const errs = Array.from(modal.querySelectorAll('.el-form-item__error, [class*=error], [class*=tip], .warning, [class*=required]'))
            .map(e => (e.innerText||'').trim()).filter(t => t.length > 0);
        return {
            modalText: modal.innerText.slice(0, 500),
            errors: errs.slice(0, 20)
        };
    }""")
    print(f"    {txt}")

try:
    page.screenshot(path="data/csdn_publish61.png")
    print("\n截图: data/csdn_publish61.png")
except Exception:
    pass
br.close()
