# -*- coding: utf-8 -*-
"""内置浏览器：程序自带 Chromium，登录态存在本地 profile，扫码一次长期有效。

跟"浏览器插件"路线的本质区别：
  - 插件方案：寄生在你日常用的 Chrome/Edge 里，浏览器一关就断
  - 本方案：程序自己开一个带独立 profile 的 Chromium，登录态存盘，
            可以后台常驻、可以被服务进程托管、可以给 AI 24 小时调用

每个平台一个独立 profile 目录，互不串味，也方便单独重登。

关于验证码/人机识别的立场（重要，别绕）：
  我们做的是**降低触发率 + 可交接的人工兜底**，不是对抗式破解。
  理由很简单：滑块/点选类验证码是服务端下发、前端 JS 加密上报轨迹的，
  纯脚本"硬解"的成功率随时会被风控升级归零，而且账号说封就封。
  真正稳的三层在下面 CaptchaPolicy 里写着了：
    1. 能走官方 API/令牌的绝不模拟浏览器（博客园、掘金都有）
    2. 登录态持久化，把"过验证"从每天一次压到一次性
    3. 反检测，让自动化浏览器看起来就是普通浏览器，从源头少弹验证
  剩下那点必须人工的，就交给 watchdog 暂停 + 人工过完自动续跑。
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


# ---------------------------------------------------------------------------
# 虚拟显示：Linux 服务器/容器里没有 X Server，有头浏览器（登录必须用）起不来。
# 这里自动兜一层 Xvfb，让"扫码登录"在云主机上也能用。
# ---------------------------------------------------------------------------
_XVFB = None


def _sock_path(disp):
    try:
        n = disp.split(":")[-1].split(".")[0]
        return Path(f"/tmp/.X11-unix/X{n}")
    except Exception:
        return None


def _xvfb_running(disp):
    """有没有 Xvfb 进程正在服务这个 display。"""
    try:
        r = subprocess.run(["pgrep", "-f", f"Xvfb {disp}"],
                           capture_output=True, text=True, timeout=5)
        return bool(r.stdout.strip())
    except Exception:
        return False


def _display_alive(disp):
    """DISPLAY 环境变量常常是"僵尸值"——容器里被塞了 :0，或者上次 Xvfb 死了
    但 /tmp/.X11-unix/X99 的 socket 文件还留着。两种情况都会让有头浏览器直接崩。

    所以按"进程在 + 真能连上"双重确认，socket 存在与否不作为判据。
    """
    if not disp:
        return False
    # 1) xdpyinfo 真连一次，最可靠
    if shutil.which("xdpyinfo"):
        try:
            r = subprocess.run(["xdpyinfo", "-display", disp],
                               capture_output=True, timeout=6)
            if r.returncode == 0:
                return True
        except Exception:
            pass
        # 连不上，但如果有 Xvfb 进程刚起来可能还没就绪，再给一次机会
        if _xvfb_running(disp):
            time.sleep(1.2)
            try:
                r = subprocess.run(["xdpyinfo", "-display", disp],
                                   capture_output=True, timeout=6)
                return r.returncode == 0
            except Exception:
                pass
        return False
    # 2) 没有 xdpyinfo，退而求其次看进程
    return _xvfb_running(disp)


def _reap_dead_socket(disp):
    """清掉残留的死 socket，否则 Xvfb 会认为该 display 已被占用而启动失败。"""
    sock = _sock_path(disp)
    if sock and sock.exists() and not _xvfb_running(disp):
        try:
            sock.unlink()
            return True
        except Exception:
            pass
    return False


def ensure_display():
    """拿到一个**真的能用**的 DISPLAY，不行就自己拉一个 Xvfb。

    踩过的坑（别改回去）：
      - 容器里 DISPLAY 常是僵尸值 :0，盲信它 → 有头浏览器崩
      - Xvfb 进程死了但 /tmp/.X11-unix/Xn 还在 → 新 Xvfb 起不来 → 全部候选跳过
        → 静默降级成无头 → 验证码永远过不去，还查不出为什么
    """
    global _XVFB
    if sys.platform not in ("linux", "linux2"):
        return os.environ.get("DISPLAY")       # Win/mac 有真桌面

    # 先看当前 DISPLAY 是不是真活着
    cur = os.environ.get("DISPLAY")
    if cur and _display_alive(cur):
        return cur
    if cur:
        os.environ.pop("DISPLAY", None)        # 僵尸值，扔掉

    if not shutil.which("Xvfb"):
        return None                            # 没装，调用方自己降级

    # 号段给宽一点，并且先清死 socket，避免被上次残留卡死
    for num in list(range(99, 79, -1)) + list(range(120, 140)):
        disp = f":{num}"
        if _xvfb_running(disp):                # 有人在服务，直接复用
            if _display_alive(disp):
                os.environ["DISPLAY"] = disp
                return disp
            continue
        _reap_dead_socket(disp)                # 清残留，否则启动必失败
        try:
            p = subprocess.Popen(
                ["Xvfb", disp, "-screen", "0", "1600x1000x24", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            if p.poll() is not None:           # 秒退 = 起来失败
                continue
            if _display_alive(disp):
                _XVFB = p
                os.environ["DISPLAY"] = disp
                return disp
            p.terminate()                      # 起来了但连不上，换一个
        except Exception:
            continue
    return None


def stop_display():
    global _XVFB
    if _XVFB:
        try:
            _XVFB.terminate()
        except Exception:
            pass
        _XVFB = None

ROOT = Path(__file__).resolve().parent.parent
PROFILE_ROOT = ROOT / "data" / "profiles"
DEBUG_DIR = ROOT / "data" / "debug"
CAPTCHA_DIR = ROOT / "data" / "captcha"

# ---------------------------------------------------------------------------
# 反检测。各家风控盯的无非是这几个点，逐条抹平。
# 注意：这些是"别露馅"，不是"攻击"——目的只是让自动化浏览器不被一眼看穿。
# ---------------------------------------------------------------------------
STEALTH_JS = """
// 1) navigator.webdriver —— 最经典的一个指纹，headless 下恒为 true
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
delete Object.getPrototypeOf(navigator).webdriver;

// 2) 语言/插件：无头环境默认是空的，一眼假
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
Object.defineProperty(navigator, 'plugins', {
  get: () => [
    { name: 'PDF Viewer' }, { name: 'Chrome PDF Viewer' },
    { name: 'Chromium PDF Viewer' }, { name: 'Microsoft Edge PDF Viewer' },
    { name: 'WebKit built-in PDF' }
  ]
});

// 3) window.chrome：真 Chrome 有，Playwright 里没有
window.chrome = window.chrome || { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };

// 4) permissions.query 对 notifications 的行为差异
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (p) =>
  p.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : origQuery(p);

// 5) WebGL 指纹：无头下 vendor/renderer 会暴露 SwiftShader
const getParam = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function (p) {
  if (p === 37445) return 'Intel Inc.';                       // UNMASKED_VENDOR_WEBGL
  if (p === 37446) return 'Intel Iris OpenGL Engine';          // UNMASKED_RENDERER_WEBGL
  return getParam.call(this, p);
};

// 6) 硬件参数：0 核 0 内存也一眼假
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// 7) 无头下 outerWidth/Height 等于 inner，是个破绽
if (window.outerWidth === 0) {
  Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
  Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 88 });
}

// 8) 有的风控会检测 CDP 注入的 Runtime.enable 痕迹
try {
  const origToString = Function.prototype.toString;
  Function.prototype.toString = function () {
    if (this === origToString) return 'function toString() { [native code] }';
    return origToString.call(this);
  };
} catch (e) {}
"""

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 启动参数：把能泄露自动化的开关全关掉
LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",   # 关键：去掉 navigator.webdriver 的来源
    "--disable-features=IsolateOrigins,site-per-process,AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--window-size=1440,900",
]


# ---------------------------------------------------------------------------
# 验证码策略
# ---------------------------------------------------------------------------
class CaptchaPolicy:
    """验证码处置策略。

    顺序很重要：先想办法**不遇到**，再想办法**遇到一次就完事**，
    最后才是遇到时怎么办。
    """
    # 各平台验证码特征，命中就交给对应策略
    PATTERNS = {
        "geetest":      ["geetest", "gt-", "极验"],
        "aliyun":       ["nc_", "aliyuncs.com/captcha", "阿里云验证"],
        "tencent":      ["tcaptcha", "腾讯验证"],
        "hcaptcha":     ["hcaptcha"],
        "recaptcha":    ["recaptcha", "grecaptcha"],
        "slide":        ["slider", "滑块", "拖动滑块", "按住滑块"],
        "sms":          ["短信验证", "获取验证码", "手机验证"],
        "manual_risk":  ["安全验证", "确认您不是机器人", "CertifyId", "访问验证", "人机验证"],
    }

    # 哪些平台纯协议就能发，压根不用开浏览器 —— 这是最彻底的"绕过"
    API_FIRST = {
        "cnblogs": "MetaWeblog XML-RPC，只需访问令牌，零验证码",
        "juejin":  "有内容 OpenAPI，但需申请；默认仍走浏览器",
    }

    # 各类验证码里"需要点的那个东西"的选择器，按平台优先级排
    CHECK_HINTS = [
        # 阿里云（博客园用的就是这个，"确认您不是机器人"）
        ".aliyun-captcha-checkbox", "#aliyunCaptcha .checkbox",
        "[class*='aliyunCaptcha'] [class*='checkbox']",
        # 极验
        ".geetest_radar_tip", ".geetest_btn", "[class*='geetest'] [class*='btn']",
        # 腾讯
        ".tcaptcha-checkbox", "#tcaptcha_iframe", "[class*='tcaptcha'] [class*='checkbox']",
        # reCAPTCHA（recaptcha.net 国内镜像）
        ".recaptcha-checkbox-border", "#recaptcha-anchor",
        # 通用
        "input[type=checkbox][class*=captcha]",
        "[class*='captcha'] [class*='checkbox']",
        "[class*='verify'] [class*='checkbox']",
    ]
    # 滑块相关
    SLIDER_HINTS = [
        ".btn_slide", ".nc_iconfont.btn_slide", "[class*='slider-btn']",
        "[class*='slide-btn']", "[class*='slider'] [class*='btn']",
        ".geetest_slider_button", "[class*='sliderButton']",
    ]

    def __init__(self):
        self.paused = False
        self.hit = None      # 最近一次命中的验证码类型

    @classmethod
    def detect(cls, page):
        """扫页面文本+DOM 特征，判断当前是不是卡在验证码上。"""
        try:
            html = (page.content() or "").lower()
            for kind, keys in cls.PATTERNS.items():
                if any(k.lower() in html for k in keys):
                    return kind
        except Exception:
            pass
        # 独立的验证码 iframe 也算
        try:
            for fr in page.frames:
                u = (fr.url or "").lower()
                if any(s in u for s in ("captcha", "verify", "geetest", "tcaptcha")):
                    return "iframe_captcha"
        except Exception:
            pass
        return None

    @classmethod
    def detections(cls, page):
        hits = []
        try:
            html = (page.content() or "").lower()
            for kind, keys in cls.PATTERNS.items():
                if any(k.lower() in html for k in keys):
                    hits.append(kind)
        except Exception:
            pass
        return hits

    # ---------------- 半自动处置 ----------------

    @classmethod
    def _find(cls, page, hints, action="点击"):
        """在主文档和各 iframe 里找一个存在的目标。返回 (locator, frame_url)。"""
        for f in [page] + list(page.frames):
            try:
                for sel in hints:
                    loc = f.locator(sel)
                    if loc.count():
                        return loc.first, (getattr(f, "url", "") or "main")
            except Exception:
                continue
        return None, None

    @classmethod
    def try_auto_pass(cls, page, timeout=25):
        """半自动尝试过掉验证。

        注意定位：这不是"破解"，是在**验证码本身简单**（纯复选框）时省你一次手点。
        需要在服务端做行为判定的（滑块、点选、reCAPTCHA 打分），大概率过不去，
        过不去就交给人工 —— 见 wait_human_captcha。

        返回 (passed: bool, detail: str)
        """
        from core import humanize
        kind = cls.detect(page)
        if not kind:
            return True, "没有验证码"

        detail = []

        # 1) 先试纯复选框 —— 这类最可能自动过
        loc, where = cls._find(page, cls.CHECK_HINTS)
        if loc:
            try:
                box = loc.bounding_box()
                if box:
                    cx = box["x"] + box["width"] / 2
                    cy = box["y"] + box["height"] / 2
                    # 带轨迹地移动过去再点，别用 locator.click
                    humanize.human_click(page, x=cx, y=cy)
                    detail.append("已拟人点击复选框")
                    # 等判定结果
                    for _ in range(int(timeout / 1.5)):
                        time.sleep(1.5)
                        if not cls.detect(page):
                            return True, "；".join(detail) + " → 通过"
                    detail.append("点了但没通过")
                else:
                    detail.append("复选框不可见")
            except Exception as e:
                detail.append(f"点复选框异常:{type(e).__name__}")

        # 2) 再试滑块 —— 拖一把，成不成都算尽力
        if kind in ("slide", "aliyun", "geetest", "tencent", "iframe_captcha"):
            sl, _ = cls._find(page, cls.SLIDER_HINTS)
            if sl:
                try:
                    box = sl.bounding_box()
                    track = None
                    # 找轨道宽度：滑块容器通常有个 track
                    for sel in ("[class*='track']", "[class*='nc_scale']",
                                "[class*='slider-track']", "[class*='bg']"):
                        t = page.locator(sel)
                        if t.count() and t.first.bounding_box():
                            track = t.first.bounding_box()
                            break
                    dist = (track["width"] - box["width"] - 6) if track else 260
                    star_x = box["x"] + box["width"] / 2
                    star_y = box["y"] + box["height"] / 2
                    page.mouse.move(star_x, star_y)
                    humanize.human_pause(0.2, 0.4)
                    humanize.slide_to(page, dist, y_offset=int(star_y))
                    detail.append(f"已拖动滑块 {int(dist)}px")
                    for _ in range(int(timeout / 1.5)):
                        time.sleep(1.5)
                        if not cls.detect(page):
                            return True, "；".join(detail) + " → 通过"
                    detail.append("拖了但判定未通过")
                except Exception as e:
                    detail.append(f"拖滑块异常:{type(e).__name__}")

        return False, ("；".join(detail) if detail else f"没找到可操作元素（类型 {kind}）")


def dump_captcha(page, platform, reason="unknown"):
    """把卡验证码时的现场存下来：截图 + HTML。
    一是给人工过验证时看着方便，二是扩平台时能拿来分析风控长什么样。"""
    CAPTCHA_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    shot = CAPTCHA_DIR / f"{platform}_{reason}_{ts}.png"
    try:
        page.screenshot(path=str(shot), full_page=False)
    except Exception:
        shot = None
    html_path = CAPTCHA_DIR / f"{platform}_{reason}_{ts}.html"
    try:
        html_path.write_text(page.content(), encoding="utf-8")
    except Exception:
        html_path = None
    return {"screenshot": str(shot) if shot else "", "html": str(html_path) if html_path else ""}


class BuiltinBrowser:
    """一个平台一个实例，用完 close()。"""

    def __init__(self, platform, account="default", headless=False, slow_mo=0,
                 proxy=None):
        self.platform = platform
        self.account = account
        self.headless = headless
        self.slow_mo = slow_mo
        self.proxy = proxy
        self.profile_dir = PROFILE_ROOT / f"{platform}_{account}"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        # 有些平台风控认 UA 和 profile 里上次的 UA 必须一致，
        # 存一份在 profile 里，避免新旧 UA 打架反而更可疑
        self._stamp = self.profile_dir / ".ua_stamp"
        self._pw = None
        self._ctx = None

    def _ua(self):
        # 首次用固定 UA；之后一直复用，别换
        if self._stamp.exists():
            try:
                return self._stamp.read_text(encoding="utf-8").strip() or UA
            except Exception:
                pass
        self._stamp.write_text(UA, encoding="utf-8")
        return UA

    def start(self):
        if self._ctx:
            return self._ctx
        # 有头模式在 Linux 上需要 X Server，没有就自动起 Xvfb
        if not self.headless:
            self.display = ensure_display()
            if not self.display:
                # 退化成"无头但有头UA"：能跑，只是用户看不见、没法手动过验证
                print("[warn] 没找到 Xvfb/DISPLAY，有头模式不可用，"
                      "已降级为无头。登录请在有桌面的机器上做，或装：apt install xvfb")
                self.headless = True
        self._pw = sync_playwright().start()
        opts = dict(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=LAUNCH_ARGS,
            ignore_default_args=["--enable-automation", "--use-mock-keychain"],
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=self._ua(),
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-platform": '"Windows"',
            },
        )
        if self.proxy:
            opts["proxy"] = self.proxy
        self._ctx = self._pw.chromium.launch_persistent_context(**opts)
        self._ctx.add_init_script(STEALTH_JS)
        return self._ctx

    @property
    def ctx(self):
        return self.start()

    def new_page(self):
        page = self.ctx.new_page()
        # 鼠标轨迹微抖动：纯瞬移点击是行为指纹里最明显的一条
        try:
            page.add_init_script("""
              (() => {
                let seed = Date.now() % 1000;
                const rnd = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
                const move = (el, x, y) => el.dispatchEvent(new MouseEvent('mousemove', {
                  clientX: x, clientY: y, bubbles: true
                }));
                document.addEventListener('click', (e) => {
                  for (let i = 0; i < 3; i++) {
                    move(document, e.clientX - rnd() * 6, e.clientY - rnd() * 6);
                  }
                }, true);
              })();
            """)
        except Exception:
            pass
        return page

    def close(self):
        try:
            if self._ctx:
                self._ctx.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._ctx = self._pw = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *a):
        self.close()


def wait_human_captcha(page, platform, timeout=300, poll=2, try_auto=True):
    """卡在验证码上时的处置：先尝试半自动，不行再把窗口交给人工。

    顺序是有讲究的：
      1. 先试 try_auto_pass —— 纯复选框那种经常能一次过，省你手动一步
      2. 过不了就转人工：窗口已经开着，你直接在里面点/拖/选就行
      3. 你过完，这里轮询发现验证码消失，自动接着往下跑

    返回 (ok, info)：ok=True 验证已通过；ok=False 超时或页面被关。
    这是有意为之的"半自动"——不硬解，只交接。
    """
    kind = CaptchaPolicy.detect(page) or "unknown"
    files = dump_captcha(page, platform, kind)

    # ---- 第一步：半自动尝试 ----
    if try_auto:
        print(f"\n>>> 检测到验证码（{kind}），先试一次半自动…")
        passed, detail = CaptchaPolicy.try_auto_pass(page, timeout=min(20, timeout))
        if passed:
            print(f">>> 半自动通过：{detail}")
            return True, {"kind": kind, "mode": "auto", "detail": detail, **files}
        print(f">>> 半自动没通过（{detail}），转人工。")

    # ---- 第二步：交人工 ----
    print(f"\n{'=' * 62}")
    print(f"  【需要人工】{platform} 弹了验证码（类型：{kind}）")
    print(f"  现场截图：{files['screenshot']}")
    print(f"  浏览器窗口已经开着，请在里面手动完成验证（点/拖/选）。")
    print(f"  过完这里会自动继续，最长等 {timeout} 秒。")
    if CaptchaPolicy.API_FIRST.get(platform):
        print(f"  小提示：{platform} 其实可以走 {CaptchaPolicy.API_FIRST[platform]}，")
        print(f"          走那条路压根不会有验证码，有空可以考虑。")
    print(f"{'=' * 62}\n")

    deadline = time.time() + timeout
    last_try = 0
    while time.time() < deadline:
        time.sleep(poll)
        try:
            if page.is_closed():
                return False, {"reason": "页面被关闭", "kind": kind, **files}
            if not CaptchaPolicy.detect(page):
                waited = round(timeout - (deadline - time.time()))
                return True, {"kind": kind, "mode": "human",
                              "waited": waited, **files}
        except Exception:
            pass
        # 每 20 秒再自动试一次（有的验证码是动态刷新的，重试可能过）
        if try_auto and time.time() - last_try > 20:
            last_try = time.time()
            try:
                p, _ = CaptchaPolicy.try_auto_pass(page, timeout=6)
                if p:
                    return True, {"kind": kind, "mode": "auto-retry", **files}
            except Exception:
                pass
    return False, {"reason": "等待人工验证超时", "kind": kind, **files}


def ensure_login(browser, login_url, check_fn, timeout=300, poll=3,
                 on_captcha="handoff"):
    """
    确认登录态。没登录就开个有头窗口让用户扫码/过验证，循环等到成功。

    check_fn(page) -> bool，由各平台适配器实现。

    on_captcha 决定遇到验证码怎么办：
      "handoff"  暂停，把窗口交给人工，过完自动续跑（默认，最稳）
      "skip"     不管验证码，只看登录态（适合你人在旁边、本来就要手动点）
      "abort"    一遇到验证码立刻放弃并报错（适合无人值守批处理）
    """
    page = browser.new_page()
    page.goto(login_url, timeout=60000, wait_until="domcontentloaded")

    if check_fn(page):
        page.close()
        return True, "已登录（复用本地登录态）"

    if browser.headless:
        page.close()
        return False, "未登录，且当前是无头模式没法扫码。请加 --headed 跑一次完成登录"

    handled = False
    print(f"\n>>> 请在弹出的浏览器里登录【{browser.platform}】，"
          f"最多等 {timeout} 秒…")
    if CaptchaPolicy.API_FIRST.get(browser.platform):
        print(f">>> 提示：{browser.platform} 可以走 {CaptchaPolicy.API_FIRST[browser.platform]}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(poll)

        # 先看有没有弹验证码
        kind = CaptchaPolicy.detect(page) if not handled else None
        if kind:
            if on_captcha == "abort":
                page.close()
                return False, f"遇到验证码（{kind}），按配置放弃"
            if on_captcha == "handoff":
                print(f">>> 检测到验证码（{kind}），切换人工模式…")
                ok, info = wait_human_captcha(page, browser.platform,
                                              timeout=max(60, int(deadline - time.time())))
                handled = True
                if not ok:
                    page.close()
                    return False, f"人工验证未完成：{info.get('reason', '')}"
                print(">>> 验证已通过，继续等待登录态…")

        try:
            if check_fn(page):
                page.close()
                return True, "登录成功，登录态已保存到本地"
        except Exception:
            pass
    page.close()
    return False, "等待登录超时"


def dump_dom(page, tag="debug"):
    """把当前页面 HTML 存下来——扩新平台时靠它看真实结构，比猜选择器快十倍。"""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / f"{tag}_{int(time.time())}.html"
    path.write_text(page.content(), encoding="utf-8")
    return path
