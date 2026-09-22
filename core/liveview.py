# -*- coding: utf-8 -*-
"""实时预览沙箱：headless 浏览器跑自动化，截图流经本地 HTTP 页面实时展示。

设计动机（用户原话：内置是把它放在应用里面，自己打开自己预览，不用拿出来外面的）：
  - 自动化浏览器全程 headless（沙箱，无窗口弹出）
  - 本模块起一个轻量 HTTP 服务（默认 127.0.0.1:8765），
    页面轮询 /shot 拿最新截图、/status 拿步骤日志
  - 在 WorkBuddy 内置浏览器面板打开 http://127.0.0.1:8765
    就能"现场看"AI 操作浏览器的全过程——不用弹出任何外部窗口

线程模型（重要，别改回去）：
  Playwright sync API 基于 greenlet，**所有调用必须在创建它的那个线程**。
  后台线程调 page.screenshot() 会直接 greenlet 崩溃
  （greenlet.error: Cannot switch to a different thread，实测 2026-09-21）。
  所以截图由主流程线程同步拍：mon.snap() 拍一帧，
  mon.sleep(n) 在等待期间每 ~1.2s 拍一帧，页面观感就是连续直播。

用法：
    from core.liveview import LiveMonitor
    with LiveMonitor(port=8765, platform="CSDN") as mon:
        page = br.start().new_page()
        mon.log("打开编辑器")
        page.goto(...)
        mon.snap(page)                 # 拍一帧
        mon.sleep(page, 8)             # 等待期间持续出帧
        ...
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>自动化沙箱实时预览</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background:#0d1117; color:#c9d1d9; font-family:"Cascadia Code",Consolas,"Microsoft YaHei",monospace;
         padding: 18px; }
  h1 { font-size: 15px; font-weight:600; color:#e6edf3; display:flex; align-items:center; gap:8px; }
  h1 .dot { width:9px; height:9px; border-radius:50%; background:#3fb950; box-shadow:0 0 8px #3fb950;
            animation: pulse 1.6s infinite; }
  @keyframes pulse { 50% { opacity:.35; } }
  .meta { font-size:12px; color:#8b949e; margin:4px 0 12px; }
  #shot { width:100%; border:1px solid #30363d; border-radius:8px; background:#161b22; display:block; }
  #status { margin-top:12px; padding:10px 14px; background:#161b22; border:1px solid #30363d;
            border-radius:8px; font-size:13px; line-height:1.7; white-space:pre-wrap; max-height:180px;
            overflow-y:auto; }
  .ok { color:#3fb950; }
  .warn { color:#d29922; }
</style>
</head>
<body>
<h1><span class="dot"></span>沙箱实时预览 <span id="plat" style="color:#8b949e;font-weight:400"></span></h1>
<div class="meta">headless 浏览器 · 无外部窗口 · 本页面运行在应用内置浏览器面板中</div>
<img id="shot" alt="等待第一帧截图…">
<div id="status">正在连接…</div>
<script>
const qs = new URLSearchParams(location.search);
document.getElementById('plat').textContent = qs.get('p') ? '· ' + qs.get('p') : '';
const img = document.getElementById('shot');
const st = document.getElementById('status');
let lastTs = '';
setInterval(async () => {
  try {
    const r = await fetch('/status', {cache: 'no-store'});
    const j = await r.json();
    if (j.ts && j.ts !== lastTs) {
      lastTs = j.ts;
      img.src = '/shot?t=' + Date.now();
      img.alt = '实时截图';
    }
    st.innerHTML = j.lines.map(l => {
      if (l.includes('✓') || l.includes('成功')) return '<div class="ok">' + l + '</div>';
      if (l.includes('警告') || l.includes('失败') || l.includes('✗')) return '<div class="warn">' + l + '</div>';
      return '<div>' + l + '</div>';
    }).join('');
    st.scrollTop = st.scrollHeight;
  } catch (e) { /* 服务停了就静默 */ }
}, 1200);
</script>
</body>
</html>"""


class LiveMonitor:
    """截图流 + 步骤日志 + 轻量 HTTP 服务。with 语法自动清理。

    注意：snap()/sleep() 必须在创建 Playwright 对象的同一个线程里调用。
    """

    def __init__(self, port=8765, platform=""):
        self.port = port
        self.platform = platform
        self._lock = threading.Lock()
        self.lines = []          # 状态日志（页面上滚动显示）
        self.ts = ""             # 最近一帧时间戳（变了页面才换图）
        self._shot_bytes = b""
        self._server = None

    # ---------- 对外 API ----------

    def log(self, msg):
        """记录一步（页面实时可见）。"""
        stamp = time.strftime("%H:%M:%S")
        with self._lock:
            self.lines.append(f"[{stamp}] {msg}")
            self.lines = self.lines[-40:]
        print(f"[live] {msg}", flush=True)

    def snap(self, page):
        """拍一帧（主线程调用）。"""
        try:
            buf = page.screenshot(type="jpeg", quality=62)
            with self._lock:
                self._shot_bytes = buf
                self.ts = time.strftime("%H:%M:%S")
        except Exception:
            pass  # 页面导航中/已关闭

    def attach_cdp(self, page):
        """体检 D11 修复（QA 标质力 2026-09-21）：接入发布链路的持续画面流。

        用 CDP Page.startScreencast 让浏览器在**每次重绘时主动推帧**，
        解决"截图线程跨线程调 Playwright 必崩（greenlet）"的死结——
        帧事件由 Playwright 在页面操作期间自动分发到本线程，不额外开线程。
        注意：帧只在页面重绘时产生（导航/弹窗/DOM 变化），纯 Python sleep
        期间不会有新帧——页面观感是"操作时有画面"，配合步骤日志足够看懂流程。
        必须在创建 page 的那个线程里调用。
        """
        try:
            cdp = page.context.new_cdp_session(page)
            mon = self

            def on_frame(params):
                data = params.get("data") or ""
                if data:
                    import base64
                    with mon._lock:
                        mon._shot_bytes = base64.b64decode(data)
                        mon.ts = time.strftime("%H:%M:%S")
                try:
                    cdp.send("Page.screencastFrameAck",
                             {"sessionId": params.get("sessionId")})
                except Exception:
                    pass

            cdp.on("Page.screencastFrame", on_frame)
            cdp.send("Page.startScreencast",
                     {"format": "jpeg", "quality": 60,
                      "maxWidth": 1440, "maxHeight": 900, "everyNthFrame": 1})
            self._cdp = cdp
            return True
        except Exception as e:
            print(f"[live] CDP 截屏挂载失败，回退手动 snap 模式: {e}", flush=True)
            return False

    def sleep(self, page, seconds, every=1.2):
        """等待 seconds 秒，期间每 every 秒出一帧（伪直播）。"""
        end = time.time() + seconds
        while True:
            remain = end - time.time()
            if remain <= 0:
                break
            self.snap(page)
            time.sleep(min(every, remain))

    def start(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), self._make_handler())
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        # port=0 时由系统分配空闲端口，回填真实端口（并发多任务各用一个端口）
        self.port = self._server.server_address[1]
        print(f"[live] 实时预览: {self.url()}", flush=True)
        return self

    def stop(self):
        try:
            if self._server:
                self._server.shutdown()
        except Exception:
            pass
        print("[live] 预览服务已停止", flush=True)

    def url(self):
        return f"http://127.0.0.1:{self.port}/?p={self.platform}"

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()

    # ---------- 内部 ----------

    def _make_handler(self):
        mon = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # 静音默认访问日志
                pass

            def _send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.startswith("/shot"):
                    with mon._lock:
                        buf = mon._shot_bytes
                    if buf:
                        self._send(200, buf, "image/jpeg")
                    else:
                        self._send(204, b"", "image/jpeg")
                elif self.path.startswith("/status"):
                    with mon._lock:
                        payload = {"ts": mon.ts, "lines": list(mon.lines)}
                    self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                               "application/json; charset=utf-8")
                else:
                    self._send(200, _PAGE_HTML.encode("utf-8"), "text/html; charset=utf-8")

        return H
