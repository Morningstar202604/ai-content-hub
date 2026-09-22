# -*- coding: utf-8 -*-
"""拟人化点击实测：全程贝塞尔轨迹 + 真实鼠标事件（回答"你有没有试过"）。

验证目标：
  1. human_click（轨迹移动）能否替代 locator.click 打开发布弹窗
  2. 分类专栏的**真用户路径**：点"新建分类专栏"展开面板 → 真实点击可见 label
     （此前一直走 JS label click 的捷径，这次试真人路线）
  3. 摘要用 human_type（带打错退格的拟人输入）
  4. 弹窗底部按钮（保存为草稿）接受**真实鼠标点击**吗
     （此前 locator.click 被拦、JS click 是捷径；raw mouse click 是关键验证）
草稿模式收尾，不发公开文章。
"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
from core.adapters.csdn import CSDNAdapter
from core import humanize

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
ad = CSDNAdapter()
assert ad.check_auth(page), "未登录"
print("登录 OK")

page.goto("https://editor.csdn.net/md/", timeout=60000, wait_until="domcontentloaded")
try:
    page.wait_for_selector("pre.editor__inner[contenteditable=true]", timeout=30000)
except Exception:
    pass
time.sleep(3)

def check(name, ok, detail=""):
    print(f"  [{'✓' if ok else '✗'}] {name} {detail}")

# 1) 导入正文（文件注入，真人也是选文件，等效）
content_md = Path("data/test_article.md").read_text(encoding="utf-8")
ok = ad._import_md_file(page, content_md)
check("正文导入", ok)

# 2) 标题：拟人路径（强制显示 + 轨迹点击 + human_type）
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
page.keyboard.press("Control+A")
page.keyboard.press("Delete")
humanize.human_type(page, ".article-bar__title--input", "拟人化点击实测：Python协程全景解析")
shown = page.evaluate("() => (document.querySelector('.article-bar__title-display')||{}).innerText || ''")
page.evaluate("""(o) => {
    const input = document.querySelector('.article-bar__title--input');
    if (input) input.setAttribute('style', o);
}""", orig or "")
check("标题注入(拟人)", shown.replace(" ", "") == "拟人化点击实测：Python协程全景解析", f"display={shown!r}")

# 3) human_click 打开发布弹窗（真实轨迹点击）
humanize.human_click(page, ".btn-publish")
time.sleep(8)
modal_open = page.evaluate("() => !!document.querySelector('.modal__button-bar')")
check("发布弹窗(human_click)", modal_open)

# 4) 分类专栏真用户路径：点"新建分类专栏"展开面板
btns = page.locator('.modal__inner-2 button.tag__btn-tag')
new_cat_btn = None
for i in range(btns.count()):
    if "新建分类专栏" in btns.nth(i).inner_text():
        new_cat_btn = i
        break
print(f"  新建分类专栏按钮 idx={new_cat_btn}")
if new_cat_btn is not None:
    humanize.human_click(page, f'.modal__inner-2 button.tag__btn-tag >> nth={new_cat_btn}')
    time.sleep(2.5)
    vis = page.evaluate("""() => {
        const c = document.querySelector('.tag__options-content');
        if (!c) return null;
        const r = c.getBoundingClientRect();
        return {disp: window.getComputedStyle(c).display, w: r.width|0, h: r.height|0,
                x: r.x|0, y: r.y|0};
    }""")
    print(f"  面板展开状态: {vis}")
    if vis and vis["w"] > 0:
        # 面板开了！真实点击可见 label
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
        print(f"  label 坐标: {lbl}")
        if lbl:
            humanize.human_click(page, x=lbl["x"], y=lbl["y"])
            time.sleep(1.5)
            cat = page.evaluate("() => document.querySelector('.tag__box input[type=hidden][name=categories]')?.value")
            chk = page.evaluate("() => document.querySelector('input.tag__option-chk[value=后端与架构设计]')?.checked")
            check("分类(真用户路径)", cat == "后端与架构设计", f"categories={cat!r} checked={chk}")
    else:
        # 面板没开（headless 下 dropdown 打不开），降级 JS label click 并记录
        print("  [!] 面板未展开（headless 限制），降级 JS label click")
        page.evaluate("""() => {
            const inps = document.querySelectorAll('input.tag__option-chk');
            for (const c of inps) { if (c.value === '后端与架构设计') {
                const lbl = c.closest('label'); if (lbl) lbl.click(); else c.click(); } }
        }""")
        time.sleep(1)
        cat = page.evaluate("() => document.querySelector('.tag__box input[type=hidden][name=categories]')?.value")
        check("分类(JS降级)", cat == "后端与架构设计", f"categories={cat!r}")

# 5) 摘要：human_click + human_type（拟人输入含打错退格）
ta_box = page.evaluate("""() => {
    const ta = document.querySelector('textarea.el-textarea__inner');
    if (!ta) return null;
    const r = ta.getBoundingClientRect();
    return {x: r.x + r.width/2, y: r.y + 12};
}""")
if ta_box:
    humanize.human_click(page, x=ta_box["x"], y=ta_box["y"])
    humanize.human_type(page, "textarea.el-textarea__inner", "拟人化点击实测：全程轨迹移动与真实鼠标事件。")
    val = page.evaluate("() => document.querySelector('textarea.el-textarea__inner')?.value")
    check("摘要(human_type)", bool(val and len(val) > 10), f"len={len(val or '')}")

# 6) 标签：真实轨迹点击面板里的 el-tag
try:
    ad._select_tag(page, "Python")  # 现有逻辑已是真实点击（locator.click）
    tag_list = page.evaluate("""() => {
        const box = document.querySelector('.tag__box');
        return box ? box.innerText.trim().slice(0, 60) : null;
    }""")
    check("标签选择", True, f"tag区={tag_list!r}")
except Exception as e:
    print(f"  [!] 标签: {e}")

# 7) 关键验证：弹窗底部按钮接受真实鼠标点击吗（保存为草稿 = 同款按钮栏）
#    抓真实点击后的请求，看链路是否触发
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
print(f"\n保存为草稿按钮坐标: {btn}")
if btn:
    humanize.human_click(page, x=btn["x"], y=btn["y"])   # 真实鼠标事件（trusted click）
    time.sleep(5)
    modal_still = page.evaluate("() => !!document.querySelector('.modal__button-bar')")
    check("草稿保存(真实鼠标点击)", not modal_still, f"弹窗关闭={not modal_still} 请求={reqs[:3]}")
    print(f"  捕获请求: {reqs[:6]}")

# 最终状态
time.sleep(3)
print(f"\n最终 URL: {page.url}")
try:
    page.screenshot(path="data/human_test_final.png")
except Exception:
    pass
br.close()
