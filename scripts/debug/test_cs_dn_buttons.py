"""CSDN 发布弹窗按钮 dump - 找正确选择器"""
import sys
sys.path.insert(0, '.')
import core.service as sv
from core.adapters.base import get_adapter
from core.browser import BuiltinBrowser

ad = get_adapter('csdn')
br = BuiltinBrowser('csdn', 'default', headless=True)
page = br.start().new_page()
page.goto(ad.new_url, timeout=60000, wait_until='domcontentloaded')
import time
time.sleep(5)

# 文件导入
ok = ad._import_md_file(page, open('data/test_article.md', 'r', encoding='utf-8').read())
print(f"import: {ok}")
time.sleep(2)

# 设标题
page.evaluate("""(t) => {
    const input = document.querySelector('.article-bar__title--input');
    if (input) {
        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        s.call(input, t);
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new Event('change', {bubbles: true}));
    }
}""", "CSDN 测试文章")
time.sleep(1)

# 点 .btn-publish
btn = page.query_selector('.btn-publish')
if btn and btn.is_visible():
    btn.click()
    time.sleep(10)

# dump 所有可见按钮（含 title 属性）
js = """() => {
  const btns = Array.from(document.querySelectorAll('button, a[role=button], [class*=btn]')).filter(b => {
    return b.offsetParent !== null && (b.innerText||b.title||'').trim().length > 1;
  });
  return btns.map(b => ({
    text: (b.innerText||b.title||'').trim().slice(0,40),
    cls: String(b.className||'').slice(0,60),
    tag: b.tagName,
    disabled: b.disabled || false
  }));
}"""
btns = page.evaluate(js)
print(f"\n=== all visible buttons ({len(btns)}) ===")
for b in btns:
    print(f"  [{b['tag']}] {b['text'][:40]:40s} | {b['cls'][:50]}")

# 查弹窗
js2 = """() => {
  const modal = document.querySelector('.el-dialog, .publish-article-modal, [class*=modal]');
  if (!modal) return {noModal: true};
  const footer = modal.querySelector('.el-dialog__footer, [class*=footer]');
  const footerBtns = footer ? Array.from(footer.querySelectorAll('button')).map(b => ({
    text: (b.innerText||b.title||'').trim(),
    cls: String(b.className||'').slice(0,50),
    disabled: b.disabled
  })) : [];
  return {
    modalText: (modal.innerText||'').slice(0,300),
    footerBtns: footerBtns
  };
}"""
modal = page.evaluate(js2)
print(f"\nmodal: {modal}")
br.close()
