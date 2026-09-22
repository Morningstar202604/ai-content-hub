# -*- coding: utf-8 -*-
"""dump CSDN 管理页 tmp 行结构。"""
import sys, time, json

sys.path.insert(0, ".")
from core.browser import BuiltinBrowser

br = BuiltinBrowser("csdn", "default", headless=True)
page = br.start().new_page()
page.goto("https://mp.csdn.net/mp_blog/manage/article?businessType=blog",
          timeout=60000, wait_until="domcontentloaded")
time.sleep(7)

# 找 tmp89nwlmai 文本所在的各级祖先链
info = page.evaluate("""() => {
    const walk = (el, depth, acc) => {
        if (!el || depth > 5) return;
        acc.push({d: depth, tag: el.tagName, cls: String(el.className||'').slice(0, 70),
                  text: (el.innerText||'').slice(0, 80).replace(/\\n/g, '|')});
        walk(el.parentElement, depth + 1, acc);
    };
    // 找含 tmp 的最内层元素
    const all = Array.from(document.querySelectorAll('*'));
    const innermost = all.find(e => e.children.length === 0 && (e.textContent||'').includes('tmp89nwlmai'));
    if (!innermost) return {found: false, bodySnippet: document.body.innerText.slice(0, 600)};
    const acc = [];
    walk(innermost, 0, acc);
    // 同一行内的所有可点元素（取链上第 3 层祖先作为行容器）
    const rowEl = acc.length > 3 ? acc[3] : null;
    // 用 class 反查
    let row = null;
    for (const a of acc) {
        if (a.cls && /item|row|tr|list/i.test(a.cls)) { row = a; break; }
    }
    // 在 innermost 祖先里找按钮
    const btns = [];
    let p = innermost;
    for (let i = 0; i < 7 && p; i++) {
        for (const b of p.querySelectorAll('a, button, span[class*=btn], div[class*=operate]')) {
            const t = (b.innerText||'').trim();
            if (t && t.length < 10 && !btns.some(x => x.t === t)) {
                btns.push({t, cls: String(b.className||'').slice(0, 50), depth: i});
            }
        }
        p = p.parentElement;
    }
    return {found: true, chain: acc, row, btns: btns.slice(0, 25)};
}""")
print(json.dumps(info, ensure_ascii=False, indent=1)[:3000])
br.close()
