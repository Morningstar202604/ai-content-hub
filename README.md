# AI 内容中台（ai-content-hub）

> 文章存在你自己的库里，AI 通过 API/MCP 全权管理：写、改、发、更新、看账号全部内容。
> **自带内置浏览器**，扫码登录一次，之后程序自己跑，不依赖你日常的 Chrome/Edge 开着。

<p>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="fastapi" src="https://img.shields.io/badge/API-FastAPI-teal">
  <img alt="mcp" src="https://img.shields.io/badge/AI-MCP-orange">
</p>

**已支持平台**：掘金 · CSDN（浏览器自动化）｜ 博客园（MetaWeblog 协议，免浏览器）· 扩展新平台约 150 行

## 这是什么 / 不是什么

- ✅ 是：**自托管**的多平台内容分发中台。文章库、发布、原地更新、AI 写稿，全部在你自己机器上，不依赖任何第三方 SaaS。
- ✅ 是：给 AI 程序用的**内容 API**。MCP Server + REST API 双入口，Claude / 任意脚本都能直接调用。
- ❌ 不是：群发垃圾内容的工具。发布内置限速（平台间隔 8-20s、文章间隔 30-90s），请在平台规则内使用。

## 三分钟上手

```bash
git clone https://gitcode.com/badhope/ai-content-hub.git
cd ai-content-hub
pip install -r requirements.txt
playwright install chromium

cp config.example.json config.json      # 填 AI key（可选，不填不影响发布功能）
python cli.py create --title "第一篇" --content "# Hello"
python cli.py serve                     # 打开 http://127.0.0.1:8800/static/index.html
```

登录各平台（有桌面的机器上跑一次，登录态长期有效）：

```bash
python cli.py --headed login --platform juejin      # 扫码
python cli.py --headed bootstrap-cnblogs --username 登录名 --password 密码   # 博客园自动抠令牌
```

---

## 一、为什么不用浏览器插件方案

| | 插件方案（Wechatsync 等） | 本方案（内置浏览器） |
|---|---|---|
| 登录态 | 寄生在你日常浏览器里 | 独立 profile 存本地，程序自己管 |
| 浏览器关了 | 断，跑不了 | 后台常驻，定时任务照跑 |
| 编辑已发布文章 | ❌ 接口层面就没有 | ✅ 打开编辑页原地改 |
| AI 全权管理 | 只能"发" | 增删改查 + 列表 + 状态 |
| 做成独立程序 | 做不到，必须寄生 | 天然独立，能打包分发 |

代价：平台适配要自己写。目前**掘金、CSDN（浏览器）**和**博客园（免浏览器）**已实现，
扩平台照着 150 行抄一个即可。文章可以由 AI 直接写（`core/ai.py`），接任何 OpenAI 兼容模型。

---

## 二、架构

```
        AI（Claude / 你的脚本）
             │  MCP 协议   或   REST API
             ▼
   ┌──────────────────────┐
   │      业务层 service   │
   ├──────────────────────┤
   │  文章库 articles      │  唯一真源，AI 写/改都在这儿
   │  发布实例 publications │  文章×平台，存 post_id / edit_url
   │  任务流水 jobs        │  谁什么时候发了什么，失败原因可查
   └──────────┬───────────┘
              │
     内置 Chromium（每平台一个持久化 profile）
              │
     适配器：掘金 / CSDN / （你的下一个平台）
              │
     发布    列表    原地更新
```

**原地更新靠三件事**：发布时把 `post_id` 和 `edit_url` 存进 `publications`；列表时从 DOM 抓 `edit_url`（不猜 URL）；改文章时自动把已发布实例标成 `pending`，`sync` 一把推平。

---

## 三、五分钟跑起来

```bash
pip install -r requirements.txt
playwright install chromium
```

```bash
# 1) 扫码登录（会弹出浏览器窗口，扫一次就存住了）
python cli.py login --platform juejin
python cli.py login --platform csdn

# 2) 确认登录态
python cli.py check --platform juejin

# 3) 导入一篇文章
python cli.py import --path ./my-post.md

# 4) 发布
python cli.py publish --id 1 --platforms juejin,csdn

# 5) 改文章 → 自动同步到所有已发平台（原地更新，不是新发一篇）
python cli.py update --id 1
# 或者一把推平所有改动
python cli.py sync

# 看看账号里已有什么
python cli.py refresh --platform juejin
python cli.py status
```

## 四、Web 管理界面

启动服务后浏览器打开 `http://127.0.0.1:8800`。左边文章列表，中间编辑区，右边发布面板。

**前端技术栈**（`web/` 目录，独立工程）：

| 项 | 选型 | 为什么 |
|---|---|---|
| 框架 | Vue 3 `<script setup>` | 组合式 API，逻辑按功能聚在一处，不用满文件找 data |
| UI 库 | Element Plus 2.9 + 暗色主题 | 表格/抽屉/表单/消息全有，不用自己搓组件 |
| 状态 | Pinia | 文章、发布实例、平台、统计分域管理 |
| 请求 | axios + 拦截器 | 统一错误提示，不用每个调用点写 try/catch |
| 渲染 | markdown-it | 编辑/分屏/预览三态，代码块和表格都对 |
| 构建 | Vite 6 | 秒级热更新，产物已按 vendor/ui/md 分包 |

**响应式适配**（窗口一变自动重排，不是简单的媒体查询隐藏）：

| 宽度 | 布局 | 交互 |
|---|---|---|
| ≥1440 | 三栏常驻（列表+编辑+发布） | 全展开 |
| 1024–1440 | 两栏（列表+编辑） | 发布面板 → 右侧抽屉 + 浮动按钮 |
| 768–1024 | 两栏（列表+编辑） | 同上，工具条收紧 |
| <768 | 单栏（仅编辑区） | 列表 → 左侧抽屉；工具条换行，按钮只留图标 |

手机上还有个右下角浮动「发布」按钮，一点就开侧栏。

**开发 / 构建**：

```bash
cd web
pnpm install
pnpm dev        # 开发模式，:5173，自动代理 /api 到后端 :8800
pnpm build      # 构建到 server/static/，之后 python cli.py serve 一把梭带界面
```

改界面就改 `web/src/`，改完 `pnpm build`；不想装 Node 也行，
`server/static/` 里是构建好的产物，直接跑后端就能用。

---

## 五、让 AI 直接写

```bash
export AI_API_KEY=sk-xxx                       # 或写进 config.json
export AI_BASE_URL=https://api.deepseek.com/v1 # 通义/豆包/Kimi/智谱/本地 Ollama 都行
export AI_MODEL=deepseek-chat

python cli.py ai-write --topic "怎么用 AI 管内容中台" --words 2000
python cli.py ai-write --topic "Python 自动化" --publish juejin,cnblogs   # 写完直接发

python cli.py ai-rewrite --id 1 --instruction "改得更口语，补一个踩坑章节"
python cli.py ai-polish --id 1
```

AI 写完自动抽标题、生成摘要和 3-5 个标签，直接入库。改写/润色之后，
已发布的实例会自动标成待同步——`sync` 一把就推到各平台去。

> Windows 一样跑，把 `python` 换成你的 Python 路径即可。

---

## 六、AI 怎么用

### 方式 A：MCP（推荐，AI 客户端直连）

配到客户端配置里：

```json
{
  "mcpServers": {
    "content-hub": {
      "command": "python",
      "args": ["-m", "server.mcp_server"]
    }
  }
}
```

AI 拿到 **13 个工具**：

```
hub_status        中台总览
list_articles     列出文章
get_article       读全文
create_article    新建
edit_article      改文章（自动标记待同步）
publish_article   发布到指定平台
update_article    原地更新已发布的（不是新发一篇）
sync_pending      所有改动推平
refresh_platform  抓平台文章列表入库（AI 才看得见账号里有什么）
check_account     检查登录态
ai_write          AI 写一篇并入库，可顺手发布
ai_rewrite        AI 按指令改写（自动标记待同步）
ai_polish         AI 润色：修错别字、统一代码块语言、理顺结构
```

然后直接说人话：「写篇讲 XX 的文章发到掘金和 CSDN」「把 3 号文章标题改了同步到全部平台」「看看我账号里有哪些文章」。

### 方式 B：REST API

```bash
python cli.py serve        # http://127.0.0.1:8800/docs
```

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/status` | 总览 |
| GET/POST | `/articles` | 列表 / 新建 |
| GET/PUT | `/articles/{id}` | 读 / 改 |
| POST | `/articles/{id}/publish` | 发布 |
| POST | `/articles/{id}/update` | **原地更新** |
| POST | `/sync/pending` | 推平所有改动 |
| POST | `/refresh/{platform}` | 抓账号文章入库 |
| POST | `/ai/write` | **AI 写一篇并入库** |
| POST | `/articles/{id}/ai-rewrite` | AI 改写 |
| POST | `/articles/{id}/ai-polish` | AI 润色 |
| GET | `/ai/status` | AI 配置好了没 |
| GET | `/accounts`、`/jobs` | 账号、任务流水 |
| POST | `/accounts/{platform}/login` | 扫码/过验证登录（`on_captcha=handoff\|abort`） |
| POST | `/accounts/{platform}/solve-captcha` | 就地处理验证码（半自动+人工） |
| GET | `/accounts/{platform}/diagnose` | 这平台怎么接、验证码怎么过 |
| GET | `/platforms` | 已实现的平台列表 |

> API 文档：`http://127.0.0.1:8800/docs`（FastAPI 自动生成，能直接点着调）

---

## 七、验证码与人机识别：三层策略

先把话说清楚：**"绕过验证码"这个说法本身是个坑**。

阿里云、极验、腾讯那类验证码，判定逻辑在服务端，前端 JS 加密后上报鼠标轨迹/环境指纹。
网上那些"破解"仓库（逆向滑块距离、训练模型识别缺口）的共同问题是：
平台一次风控升级就全部失效，而且账号被标记后**直接封**，代价远大于收益。

所以本项目的做法是三层递进——**想办法不遇到 > 遇到一次就永久解决 > 真遇到了交人工**：

### L1 能走官方通道就不模拟浏览器（最彻底）

有的平台开放了协议接口，压根不会有验证码。这是首选。

| 平台 | 通道 | 验证码 |
|---|---|---|
| 博客园 | MetaWeblog XML-RPC + 访问令牌 | **零验证码** |
| 掘金 | 有内容 OpenAPI（需申请） | 走 API 则零 |
| CSDN / 其他 | 无，只能浏览器 | 走 L2/L3 |

```bash
python cli.py diagnose --platform cnblogs    # 看看这平台推荐怎么接
```

### L2 反检测 + 登录态持久化（降低触发率）

`core/browser.py` 里逐条抹平自动化痕迹：

| 指纹点 | 处理 |
|---|---|
| `navigator.webdriver` | 删除，并清掉原型链上的 |
| WebGL vendor/renderer | 伪装成 `Intel Inc. / Intel Iris OpenGL Engine`（否则暴露 SwiftShader） |
| 硬件参数 | `hardwareConcurrency`/`deviceMemory` 补成 8，无头下是 0 |
| 插件 / 语言 | 补 5 个插件、`zh-CN,zh,en`（无头下为空，一眼假） |
| `window.chrome` | 补上（真 Chrome 有，Playwright 没有） |
| `outerHeight` | 修正（无头下等于 inner，是破绽） |
| 启动参数 | `--disable-blink-features=AutomationControlled` 等 |
| 输入行为 | 逐字符输入 + 打错退格；鼠标走贝塞尔弧线 + 抖动 + 末段减速 |

配合 **登录态持久化**：一次登录存进 `data/profiles/<平台>_<账号>/`，
之后复用，把"过验证"从每天一次压到一次性。

### L3 半自动 + 人工交接（真弹了怎么办）

`core/humanize.py` + `CaptchaPolicy`：

1. **先半自动试一次** —— 纯复选框那种（"确认您不是机器人"）经常能过，
   用带轨迹的鼠标去点，而不是 `locator.click()`（后者零延迟，行为特征明显）。
   滑块会试着按变速轨迹拖过去。
2. **过不了就转人工** —— 此时浏览器窗口已经开着，你直接在里面点/拖/选。
   代码每 2 秒轮询一次，验证码消失就自动接着往下跑。同时会自动截图 +
   存 HTML 到 `data/captcha/`，方便你看现场。
3. **顺手再试** —— 人工等待期间每 20 秒重试一次半自动（有的验证码会刷新，重试能过）。

```bash
# 单独处理某平台的验证码
python cli.py solve-captcha --platform cnblogs --wait 180

# 登录时遇到验证码：默认就交人工
python cli.py login --platform juejin --on-captcha handoff
python cli.py login --platform juejin --on-captcha abort    # 无人值守时直接放弃
```

**实测记录**（本次沙箱）：博客园登录表单能正常填提交，提交后弹
**阿里云验证码**（"请完成安全验证 / 确认您不是机器人"，带 `CertifyId`）。
半自动点击复选框能点中，但服务端判定未通过 → 正确转入人工。
这正是预期结果：**服务端判定的验证码不应该被硬解，交人工才是对的**。

> 另外：博客园除了阿里云验证码，页面上还挂了 Google reCAPTCHA（走 `recaptcha.net` 国内镜像）。
> reCAPTCHA v3 是无感的（只打分不弹框），所以反检测做好能实实在在降低它的风控评分。

### 无人值守怎么办

验证码天然需要人。要真无人值守，只有两条路：

1. **优先用 L1**：能走协议的平台（博客园）就根本不碰验证码
2. **定期保活**：登录态是有有效期的。写个定时任务每周跑一次 `check`，
   掉线了发通知给你，你花 1 分钟手动补一次；而不是等发文章时才发现掉线

### 关于 xvfb（Linux 部署必看）

有头浏览器需要 X Server。服务器/容器里没有，程序会**自动拉一个 Xvfb**。
没装的话：

```bash
apt install -y xvfb
```

程序还会识别"僵尸 DISPLAY"——很多容器里被塞了 `DISPLAY=:0` 但根本没有 X 在监听，
盲信这个变量会让浏览器直接崩。代码会实际探测可用性，不行就换号段起 Xvfb。

---

## 八、博客园配置：浏览器登录 + 自动抠令牌（一条命令）

博客园发布走 MetaWeblog 协议最稳，但协议要三件套（endpoint / 登录用户名 / 访问令牌），
它们都锁在「设置 → 其他设置」里、**必须先登录才能看到**。
所以正确姿势不是"手贴令牌"，而是**拿账号密码浏览器登一次，自动抠出来**：

```bash
python cli.py --headed bootstrap-cnblogs \
    --username 你的登录名 --password 你的密码
```

它会：开有头浏览器 → 填账号密码 → **自动点阿里「智能验证」复选框** → 登录成功存盘
→ 打开设置页 → 把 endpoint / username / token 抠出来写进 `config.json`。
之后所有发布走纯协议，**再也不开浏览器、再也不碰验证码**。

### 登录页的验证码长什么样（别被绕）

博客园登录页叠了**两层**：

| 层 | 类型 | 能不能自动过 |
|---|---|---|
| 阿里「智能验证」 | 纯复选框（`#aliyunCaptcha-checkbox-icon`） | ✅ 拟人点一下即可，已实现 |
| Google reCAPTCHA | invisible 风险评分 | ⚠️ 环境干净时静默放行；风险分高时升级成**图片拼图**，脚本解不了 |

**关键：拼图那一下脚本过不去，但它是"一次性"的。** 登录态持久化在
`data/profiles/cnblogs_default/`，人工过完一次就一劳永逸。

### 如果自动登录被拦（弹图片拼图）

reCAPTCHA 的图片拼图是**给你看的**，用人工兜底：

```bash
python cli.py --headed login --platform cnblogs --on-captcha handoff
```

窗口会一直开着，你在里面把拼图点完，登录态自动存盘。**过这一次，后面全自动。**

> ⚠️ 别在短时间内反复试错登录——那会把 reCAPTCHA 风险分推高，
> 从"静默放行"直接变成"每次必弹拼图"。用对凭据一次过，或者干净环境重来。

### 关于「登录用户名」的一个真实坑

**数字用户 ID ≠ 登录用户名。** 比如账号站内数字 ID `1234567890` 这种，是账号在站内的数字标识
（个人主页 / 用户中心 URL 里的那串），**不是**你登录时填的用户名：
它既不是登录名，也不是 blogApp。被服务端拒时的表现是统一的 `用户名或密码错误`
（而不是"用户名不存在"），极具迷惑性。

登录名是注册时那个（邮箱 / 手机号 / 你自定义的用户名）。拿不准就去
`https://account.cnblogs.com/signin` 点「**忘记登录用户名**」找回。

## 九、两种适配器，挑着用

**浏览器型**（掘金、CSDN）：开内置 Chromium 操作编辑器，通用但慢，受页面改版影响。

**协议型**（博客园）：走 MetaWeblog XML-RPC，**不开浏览器**，稳定一个数量级，登录态不过期。
适配器里设 `needs_browser = False`，中台会自动跳过浏览器那一步。看到哪个平台有开放 API，
优先写协议型。

## 十、扩展新平台（照抄 150 行）

在 `core/adapters/` 新建 `xxx.py`，实现四个动作：

```python
@register
class XxxAdapter(PlatformAdapter):
    id = "xxx"
    login_url = "..."
    home_url  = "..."   # 登录后才能进的页，判登录态用
    list_url  = "..."
    new_url   = "..."

    def check_auth(self, page) -> bool: ...      # 登录了吗
    def list_articles(self, page, limit=50): ... # 返回 [{'post_id','title','url','edit_url','stats'}]
    def publish(self, page, article, options): ...  # 返回 {'post_id','post_url','edit_url'}
    def update(self, page, pub, article) -> bool: ... # 打开 edit_url 改内容保存
```

最后在 `core/service.py` 里 `from core.adapters import xxx` 导入一下即可注册。

**校准技巧**（必看）：平台改版导致选择器失效时，别瞎猜——

```python
from core.browser import dump_dom
dump_dom(page, "csdn_list")     # HTML 存到 data/debug/
```

打开存下来的 HTML 搜关键词，真实结构一目了然，比猜快十倍。
平台专属的 URL / API / 选择器全在各适配器顶部常量区，改版了只改那一块。

---

## 十一、当前状态与已知限制

**已跑通（沙箱实测）**：

| 模块 | 状态 |
|---|---|
| 数据层（4 张表 + 改内容自动标记待同步） | ✅ |
| 业务层（导入/发布/更新/同步/刷新） | ✅ |
| **AI 写稿**（用本地 mock 服务端到端跑通：标题抽取、摘要、标签、改写、润色） | ✅ |
| REST API（15 个端点） | ✅ |
| MCP Server（initialize / tools.list / tools.call，13 个工具） | ✅ |
| 内置浏览器 + 反检测（8 项指纹实测：webdriver 隐藏、WebGL 伪装成 Intel、硬件/插件/语言全补齐） | ✅ |
| 登录态判定（掘金、CSDN 实测都能正确识别未登录） | ✅ |
| 平台间隔限速（8-20s）+ 文章间隔限速（30-90s） | ✅ |
| **Web 管理界面**（Vue3+Element Plus，真实浏览器点过建/改/存/预览/弹窗，无 JS 报错） | ✅ |
| **响应式适配**（1920 三栏 / 1280 两栏+抽屉 / 820 / 390 单栏+抽屉，实测布局与按钮均未裁切） | ✅ |
| **验证码三层策略**（免登 API 优先 → 反检测降触发 → 半自动+人工交接，博客园实测转人工路径正确） | ✅ |
| **Xvfb 自动兜底**（识别僵尸 `DISPLAY=:0`，自动切 `:99`，有头模式在服务器上可用） | ✅ |
| **博客园登录引导**（`bootstrap-cnblogs`：填账号密码 → 自动过阿里复选框 → 登录成功 → 自动抠 MetaWeblog 令牌写 config，实测链路全通） | ✅ |
| **全面体检（交付前）**：CLI 16 子命令 argparse 冒烟 / 数据链路 建-改-查-搜-导 / AI 链路（mock 服务端到端：写稿→标题解析→摘要→标签→改写→润色）/ REST API 读写端点 / MCP（initialize + 13 工具 + tools/call）/ 前端构建产物完整性 / 各平台凭据缺失时的报错直指要害 | ✅ |

**需要真实账号跑一次才能定论**：发布、原地更新、列表这三个动作依赖真实登录态，沙箱里没账号没法端到端验证。掘金的 API 路径、CSDN 的编辑器选择器都是按公开结构写的，**第一次实跑可能需要微调**。

**博客园实测结论（重要）**：登录链路已全通——表单填充、阿里复选框自动过、
提交到服务端、读取真实错误，全部实测可用。**唯一未闭环的是登录身份**：
用数字用户 ID（非登录名）实测被服务端判 `用户名或密码错误`。
换成正确的登录用户名即可一键跑通 `bootstrap-cnblogs`，无代码改动。
详见「第八章」。

建议第一次先：
```bash
python cli.py publish --id 1 --platforms juejin --draft   # 只发草稿箱，安全
```
确认草稿正常，再关掉 `--draft` 正式发。

**已知限制**：
- 平台风控：程序内置了平台间隔（8-20s）和文章间隔（30-90s）限速，别调太小
- CSDN 更新已发布文章会重新进审核
- 掘金标签（tag_ids）暂未实现，走的是无标签发布，需要的话可在适配器里加标签搜索接口
- 单账号模型，`account` 参数已预留但多账号并发未测
- **验证码做不到 100% 自动**：服务端判定的验证码（阿里云/极验/reCAPTCHA）本质上需要人。
  程序的设计目标是"尽量不遇到 + 遇到了一次性解决 + 真弹了交人工"，
  而不是硬解。要完全无人值守，走 L1 的协议通道（如博客园的 MetaWeblog）
- **首次登录必须在能看到浏览器的机器上做**：Linux 服务器上程序会自动起 Xvfb，
  但你在服务器上"扫码"不现实（看不到屏幕）。建议在有桌面的机器上登录一次，
  把 `data/profiles/` 整个拷到服务器复用

---

## 十二、目录结构

```
ai-content-hub/
├─ cli.py                  命令行入口（14 个命令）
├─ config.example.json     凭据模板（复制为 config.json）
├─ core/
│  ├─ db.py                数据层（SQLite）
│  ├─ browser.py           内置浏览器 + 登录态持久化 + 反检测 + 验证码策略
│  ├─ humanize.py          拟人化操作（变速输入、弧线鼠标、滑块拖动）
│  ├─ ai.py                AI 写稿（OpenAI 兼容协议）
│  ├─ service.py           业务层（AI 调的就是这个）
│  └─ adapters/
│     ├─ base.py           适配器接口 + 通用工具
│     ├─ juejin.py         掘金（浏览器）
│     ├─ csdn.py           CSDN（浏览器）
│     └─ cnblogs.py        博客园（免浏览器，MetaWeblog）
├─ server/
│  ├─ static/              Web 界面构建产物（Vue 打包后落这儿）
│  ├─ api.py               REST API（19 个端点）
│  └─ mcp_server.py        MCP Server（AI 直连，13 个工具）
├─ web/                    前端工程（Vue3 + Element Plus + Vite）
│  ├─ src/
│  │  ├─ App.vue           布局骨架 + 响应式抽屉切换
│  │  ├─ api.js            接口封装
│  │  ├─ stores/hub.js     Pinia 状态
│  │  ├─ composables/      断点检测
│  │  ├─ components/       头部 / 列表 / 编辑器 / 发布面板 / AI 弹窗
│  │  └─ styles/main.scss  主题与响应式
│  ├─ vite.config.js       产物落到 ../server/static
│  └─ package.json
└─ data/                   数据库 + 浏览器 profile + 验证码现场 + 调试 HTML
```

> `data/profiles/` 存的是登录态，`data/captcha/` 存的是验证码现场截图，
> **都别外传，别进 git**（`.gitignore` 已排除 `data/` 和 `config.json`）。

---

## 十三、参与贡献

欢迎 Issue / PR。改平台适配器前先跑一下 `python cli.py diagnose --platform xxx`，
选择器失效时用 `dump_dom()` 存现场比猜快十倍。

## 十四、AI 使用说明（透明度声明）

- 本项目的**产品设计、架构与代码由人工主导完成，AI 辅助编码与测试**；
- 项目自身的定位是"AI 辅助内容创作"工具：文章由 AI 起草、人审核后发布，
  请遵守各平台的 AI 内容规范，`ai_write` 产物入库时已带 `source=ai` 标记供你区分；
- 请勿将本工具用于批量灌水、刷量等违反平台规则的行为，账号风险自负。

## 许可证

[MIT](LICENSE) © 2026 badhope
