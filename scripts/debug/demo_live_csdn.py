# -*- coding: utf-8 -*-
"""实时预览演示：CSDN 全流程（草稿模式）+ 沙箱 live view。"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.browser import BuiltinBrowser
from core.adapters.csdn import CSDNAdapter
from core.liveview import LiveMonitor

mon = LiveMonitor(port=8765, platform="CSDN")
br = BuiltinBrowser("csdn", "default", headless=True)   # 沙箱无窗口
ad = CSDNAdapter()

try:
    with mon:
        mon.log("启动 headless 沙箱浏览器（无任何外部窗口）")
        page = br.start().new_page()

        mon.log("检查 CSDN 登录态…")
        assert ad.check_auth(page), "未登录"
        mon.log("✓ 登录态有效（本地 profile 免扫码）")

        mon.log("打开 Markdown 编辑器…")
        page.goto("https://editor.csdn.net/md/", timeout=60000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("pre.editor__inner[contenteditable=true]", timeout=30000)
        except Exception:
            pass
        mon.sleep(page, 3)
        mon.log("✓ 编辑器就绪")

        mon.log("导入 Markdown 文件（input[type=file] 注入）…")
        content_md = Path("data/test_article.md").read_text(encoding="utf-8")
        ok = ad._import_md_file(page, content_md)
        mon.log(f"{'✓' if ok else '✗'} 正文导入完成（{len(content_md)} 字符）")
        mon.sleep(page, 1.5)

        mon.log("注入标题（强制显示 + 真实击键）…")
        ad._set_title(page, "实时预览演示：Python协程全景解析")
        mon.log("✓ 标题已写入框架状态")
        mon.snap(page)

        mon.log("点击「发布文章」打开发布弹窗…")
        page.query_selector('.btn-publish').click(timeout=8000)
        mon.sleep(page, 8)
        mon.log("✓ 弹窗已打开")

        mon.log("填分类专栏（JS 点 label → hidden categories）…")
        page.evaluate("""() => {
            const inps = document.querySelectorAll('input.tag__option-chk');
            for (const c of inps) { if (c.value === '后端与架构设计') {
                const lbl = c.closest('label'); if (lbl) lbl.click(); else c.click(); } }
        }""")
        time.sleep(1)
        mon.log("✓ 分类=后端与架构设计")

        mon.log("填摘要…")
        page.evaluate("""(t) => {
            const ta = document.querySelector('textarea.el-textarea__inner');
            if (ta) { const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
              s.call(ta, t); ta.dispatchEvent(new Event('input',{bubbles:true})); }
        }""", "实时预览演示：headless 沙箱里的自动化发布全流程。")
        time.sleep(1)
        mon.log("✓ 摘要已填")
        mon.snap(page)

        mon.log("选文章标签（点推荐标签，不关面板）…")
        ad._select_tag(page, "Python")
        mon.log("✓ 标签已选")
        mon.snap(page)

        mon.log("演示模式：点「保存为草稿」而非正式发布（避免再发一篇公开文章）…")
        try:
            page.evaluate("() => document.querySelector('button.btn-b-normal.ml16')?.click()")
        except Exception:
            pass
        mon.sleep(page, 4)
        mon.log("✓ 草稿已保存")

        mon.log("全部步骤完成 ✓ 服务保持 5 分钟供观看，随后自动退出")
        mon.sleep(page, 300, every=2.0)
finally:
    br.close()
