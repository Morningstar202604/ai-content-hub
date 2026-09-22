# -*- coding: utf-8 -*-
"""验证：先收起标签面板（点空白处），再真实点击保存为草稿 → 应该全通。"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
from core.adapters.csdn import CSDNAdapter
from core import humanize

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
ad = CSDNAdapter()
assert ad.check_auth(page)
print("登录 OK")

page.goto("https://editor.csdn.net/md/", timeout=60000, wait_until="domcontentloaded")
try:
    page.wait_for_selector("pre.editor__inner[contenteditable=true]", timeout=30000)
except Exception:
    pass
time.sleep(3)

content_md = Path("data/test_article.md").read_text(encoding="utf-8")
ok = ad._import_md_file(page, content_md)
print(f"导入: {ok}")

# 标题（拟人）
orig = page.evaluate("""() => {
    const input = document.querySelector('.article-bar__title--input');
    if (!input) return '';
    const o = input.getAttribute('style') || '';
    input.style.cssText += '; display:block !important; position:fixed;'
        + ' top:8px; left:8px; z-index:99999; width:420px; height:32px;'
        + ' opacity:1; background:#fff; color:#000;';
    return o;
}""")
time.sleep(0.3)
humanize.human_click(page, ".article-bar__title--input")
page.keyboard.press("Control+A"); page.keyboard.press("Delete")
humanize.human_type(page, ".article-bar__title--input", "拟人实测2：Python协程全景解析")
page.evaluate("""(o) => { const i = document.querySelector('.article-bar__title--input');
    if (i) i.setAttribute('style', o); }""", orig or "")

# 开弹窗
humanize.human_click(page, ".btn-publish")
time.sleep(8)

# 分类（真用户路径）
btns = page.locator('.modal__inner-2 button.tag__btn-tag')
for i in range(btns.count()):
    if "新建分类专栏" in btns.nth(i).inner_text():
        humanize.human_click(page, f'.modal__inner-2 button.tag__btn-tag >> nth={i}')
        break
time.sleep(2.5)
lbl = page.evaluate("""() => {
    for (const l of document.querySelectorAll('label.tag__option-label')) {
        const inp = l.querySelector('input.tag__option-chk');
        if (inp && inp.value === '后端与架构设计') {
            const r = l.getBoundingClientRect();
            if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
    }
    return null;
}""")
if lbl:
    humanize.human_click(page, x=lbl["x"], y=lbl["y"])
    time.sleep(1.5)
cat = page.evaluate("() => document.querySelector('.tag__box input[type=hidden][name=categories]')?.value")
print(f"分类: {cat!r}")

# 摘要
ta_box = page.evaluate("""() => {
    const ta = document.querySelector('textarea.el-textarea__inner');
    if (!ta) return null;
    const r = ta.getBoundingClientRect();
    return {x: r.x + r.width/2, y: r.y + 12};
}""")
if ta_box:
    humanize.human_click(page, x=ta_box["x"], y=ta_box["y"])
    humanize.human_type(page, "textarea.el-textarea__inner", "拟人化实测第二轮：先收面板再点按钮。")

# 标签（面板会保持打开）
ad._select_tag(page, "Python")

# ★ 关键步骤：点弹窗头部空白处收起标签面板（真人习惯动作）
header = page.evaluate("""() => {
    const h = document.querySelector('.publish-article-modal__header');
    if (!h) return null;
    const r = h.getBoundingClientRect();
    return {x: r.x + r.width/2, y: r.y + r.height/2};
}""")
if header:
    humanize.human_click(page, x=header["x"], y=header["y"])
    time.sleep(1.5)
panel_open = page.evaluate("""() => {
    const c = document.querySelector('.tag__options-content');
    return c ? window.getComputedStyle(c).display !== 'none' : false;
}""")
print(f"点头部后标签面板状态: open={panel_open}")

# 真实点击保存为草稿
reqs = []
def on_req(req):
    u = req.url
    if ("csdn" in u) and req.method in ("POST", "PUT") and "eva2" not in u:
        reqs.append(f"{req.method} {u[:110]}")
page.on("request", on_req)

btn = page.evaluate("""() => {
    for (const b of document.querySelectorAll('button')) {
        if ((b.innerText||'').trim() !== '保存为草稿') continue;
        const r = b.getBoundingClientRect();
        if (r.width > 10 && r.x > 0 && r.y > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
    }
    return null;
}""")
print(f"保存为草稿坐标: {btn}")
if btn:
    humanize.human_click(page, x=btn["x"], y=btn["y"])
    # 轮询 15s 看弹窗关闭
    t0 = time.time()
    closed = False
    while time.time() - t0 < 15:
        time.sleep(1.5)
        if not page.evaluate("() => !!document.querySelector('.modal__button-bar')"):
            closed = True
            break
    print(f"弹窗关闭: {closed}  耗时 {time.time()-t0:.0f}s")
    print(f"请求: {reqs[:8]}")
    print(f"URL: {page.url}")

time.sleep(2)
try:
    page.screenshot(path="data/human_test2_final.png")
except Exception:
    pass
br.close()
