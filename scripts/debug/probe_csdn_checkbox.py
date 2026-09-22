# -*- coding: utf-8 -*-
"""CSDN 目录 checkbox 结构探针：找可点击的父元素，验证真实点击能否触发框架状态。"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
import core.adapters.csdn
from core.adapters.csdn import CSDNAdapter

ad = CSDNAdapter()
br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()

if not ad.check_auth(page):
    print("CSDN 未登录")
    br.close(); sys.exit(1)
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
    if (input) {
        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        s.call(input, t);
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new Event('change', {bubbles: true}));
    }
}""", "【CSDN 探针 59】Python 协程")
ad._import_md_file(page, content_md)
time.sleep(2)

# 开弹窗
page.query_selector('.btn-publish').click(timeout=8000)
time.sleep(8)

# ===== 探针 1：每个 checkbox 的完整父链 + 可见性 =====
js = """() => {
  const inps = Array.from(document.querySelectorAll('input.tag__option-chk'));
  return inps.map((c, i) => {
    let chain = [];
    let el = c;
    for (let d = 0; d < 6 && el; d++) {
      const st = window.getComputedStyle(el);
      chain.push({
        tag: el.tagName,
        cls: String(el.className||'').slice(0, 50),
        disp: st.display,
        vis: st.visibility,
        pe: st.pointerEvents,
        pos: st.position,
        w: el.offsetWidth + 'x' + el.offsetHeight,
        opacity: st.opacity
      });
      el = el.parentElement;
    }
    return {
      i, value: c.value, checked: c.checked, disabled: c.disabled,
      type: c.type,
      name: c.name,
      label: (c.closest('label') ? c.closest('label').innerText.trim().slice(0,30) : null),
      chain
    };
  });
}"""
boxes = page.evaluate(js)
print(f"\n=== {len(boxes)} 个 checkbox 的父链结构 ===")
for b in boxes:
    print(f"\n[{b['i']}] value={b['value']!r} checked={b['checked']} disabled={b['disabled']} type={b['type']} label={b['label']!r}")
    for ci, cl in enumerate(b['chain']):
        print(f"    L{ci}: <{cl['tag']} class={cl['cls']!r}> disp={cl['disp']} vis={cl['vis']} pe={cl['pe']} pos={cl['pos']} op={cl['opacity']} size={cl['w']}")

# ===== 探针 2：尝试点击每个 checkbox 的最外层"可见"祖先，看 checked 是否变化 =====
# 先找每个 input 的可点击祖先（第一个 visible 且 pointerEvents!=none 的父）
try:
    for b in boxes[:3]:
        i = b['i']
        # 找到 value
        val = b['value']
        # 在 Playwright 侧，通过 JS 找到该 input 最近的可见祖先 label/div 的 bounding box
        bb = page.evaluate("""(val) => {
            const inps = document.querySelectorAll('input.tag__option-chk');
            let target = null;
            for (const c of inps) { if (c.value === val) { target = c; break; } }
            if (!target) return null;
            let el = target.parentElement;
            for (let d = 0; d < 6 && el; d++) {
                const st = window.getComputedStyle(el);
                if (st.display !== 'none' && st.visibility !== 'hidden' &&
                    el.offsetWidth > 0 && el.offsetHeight > 0 &&
                    st.pointerEvents !== 'none') {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        return {sel: el.tagName + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                                x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height,
                                text: (el.innerText||'').trim().slice(0,30),
                                html: el.outerHTML.slice(0,200)};
                    }
                }
                el = el.parentElement;
            }
            return null;
        }""", val)
        print(f"\n--- checkbox[{i}] value={val!r} 可点击祖先 ---")
        print(f"    {bb}")
        if bb:
            # 记录点击前 checked
            before = page.evaluate("""(val) => {
                const inps = document.querySelectorAll('input.tag__option-chk');
                for (const c of inps) { if (c.value === val) return c.checked; }
                return null;
            }""", val)
            # 用 Playwright 真实鼠标点击该祖先中心
            page.mouse.click(bb['x'], bb['y'])
            time.sleep(1)
            after = page.evaluate("""(val) => {
                const inps = document.querySelectorAll('input.tag__option-chk');
                for (const c of inps) { if (c.value === val) return c.checked; }
                return null;
            }""", val)
            print(f"    点击前 checked={before}  →  点击后 checked={after}")
except Exception as e:
    print(f"\n点击测试出错: {e}")

try:
    page.screenshot(path="data/csdn_checkbox_probe59.png")
    print("\n截图: data/csdn_checkbox_probe59.png")
except Exception:
    pass
br.close()
