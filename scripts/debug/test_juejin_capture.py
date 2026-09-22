"""掘金 publish 请求拦截 - 找真实 API 端点"""
import sys
sys.path.insert(0, '.')
import core.service as sv
from core.adapters.base import get_adapter
from core.browser import BuiltinBrowser

ad = get_adapter('juejin')
br = BuiltinBrowser('juejin', 'default', headless=True)
page = br.start().new_page()
page.goto('https://juejin.cn/editor/drafts/new', timeout=60000, wait_until='domcontentloaded')
import time
time.sleep(8)

# 拦截所有 fetch
page.evaluate("""() => {
  window._capturedReqs = [];
  const origFetch = window.fetch;
  window.fetch = function(...args) {
    const url = args[0] instanceof Request ? args[0].url : args[0];
    const opts = args[1] || {};
    window._capturedReqs.push({
      url: String(url).slice(0, 300),
      method: opts.method || 'GET',
      body: opts.body ? String(opts.body).slice(0, 600) : ''
    });
    return origFetch.apply(window, args);
  };
}""")

# 设置 CodeMirror 内容
page.evaluate("""() => {
  const ed = document.querySelector('.CodeMirror');
  if (ed && ed.CodeMirror) {
    ed.CodeMirror.setValue('# 掘金测试标题\\n\\n这是掘金测试正文内容。');
  }
}""")
time.sleep(2)

# 点发布
try:
    page.locator('button:has-text("发布")').first.click(timeout=5000)
    print("publish clicked")
except Exception as e:
    print(f"click err: {str(e)[:100]}")

time.sleep(20)

# 读所有拦截到的请求
reqs = page.evaluate("() => window._capturedReqs")
print(f"\n=== all requests ({len(reqs)}) ===")
for r in reqs:
    print(f"  {r.get('method')} {r.get('url')[:120]}")
    if r.get('body'):
        print(f"    body: {r.get('body')[:400]}")

# 查当前 URL
print(f"\nfinal URL: {page.url[:150]}")
br.close()
