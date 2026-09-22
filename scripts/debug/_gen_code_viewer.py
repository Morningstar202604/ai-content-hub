# -*- coding: utf-8 -*-
"""生成 ai-content-hub 的「完整代码查看器」单文件 HTML。

- 收集后端(core/、server/、cli.py) + 前端(web/src) 全部源文件
- config.json 的密钥脱敏（不写进 HTML）
- 侧边文件树 + 代码块（高亮）+ 全文搜索 + 折叠/展开
- 纯静态、无外部依赖、双击即开
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# (相对路径, 分组, 是否脱敏密钥)
FILES = [
    ("cli.py", "入口", False),
    ("config.json", "配置", True),
    ("requirements.txt", "入口", False),
    ("core/__init__.py", "core", False),
    ("core/service.py", "core", False),
    ("core/db.py", "core", False),
    ("core/ai.py", "core", False),
    ("core/humanize.py", "core", False),
    ("core/cnblogs_login.py", "core", False),
    ("core/browser.py", "core", False),
    ("core/adapters/base.py", "adapters", False),
    ("core/adapters/juejin.py", "adapters", False),
    ("core/adapters/csdn.py", "adapters", False),
    ("core/adapters/cnblogs.py", "adapters", False),
    ("core/adapters/jianshu.py", "adapters", False),
    ("core/adapters/zhihu.py", "adapters", False),
    ("core/adapters/toutiao.py", "adapters", False),
    ("core/adapters/bilibili.py", "adapters", False),
    ("core/adapters/oschina.py", "adapters", False),
    ("core/adapters/segmentfault.py", "adapters", False),
    ("server/api.py", "server", False),
    ("server/mcp_server.py", "server", False),
    ("web/src/main.js", "web", False),
    ("web/src/api.js", "web", False),
    ("web/src/stores/hub.js", "web", False),
    ("web/src/App.vue", "web", False),
    ("web/src/composables/useBreakpoint.js", "web", False),
    ("web/src/components/AppHeader.vue", "web", False),
    ("web/src/components/ArticleList.vue", "web", False),
    ("web/src/components/ArticleEditor.vue", "web", False),
    ("web/src/components/SidePanel.vue", "web", False),
    ("web/src/components/AIWriteDialog.vue", "web", False),
    ("web/src/components/EmptyState.vue", "web", False),
    ("web/src/components/BrandLogo.vue", "web", False),
    ("web/index.html", "web", False),
    ("web/vite.config.js", "web", False),
    ("web/package.json", "web", False),
]

SECRET_PAT = re.compile(r"sk-[A-Za-z0-9]{12,}")


def desanitize(text: str) -> str:
    # 全量打码：sk- 后 12+ 位字符一律替换，保留前 4 字符作指纹
    text = SECRET_PAT.sub(lambda m: m.group(0)[:4] + "…（已脱敏）", text)
    return text


def _lang(rel: str) -> str:
    suf = rel.rsplit(".", 1)[-1] if "." in rel else "txt"
    return {"py": "python", "js": "js", "vue": "vue", "json": "json",
            "html": "html", "scss": "scss", "css": "css", "md": "md"}.get(suf, "txt")


def read_src(rel, des):
    p = ROOT / rel
    if not p.exists():
        return "[缺失] " + rel
    t = p.read_text(encoding="utf-8", errors="replace")
    return desanitize(t) if des else t


data = []
for rel, group, des in FILES:
    src = read_src(rel, des)
    data.append({"path": rel, "group": group, "lang": _lang(rel), "lines": src.count("\n") + 1, "src": src})

GROUPS = ["入口", "配置", "core", "adapters", "server", "web"]
payload = json.dumps({"files": data, "groups": GROUPS}, ensure_ascii=False)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ai-content-hub · 完整代码查看器</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--fg:#e6edf3;--muted:#8b949e;
--accent:#58a6ff;--ok:#3fb950;--warn:#d29922;--code:#c9d1d9;--kw:#ff7b72;
--str:#a5d6ff;--com:#8b949e;--num:#79c0ff;--fn:#d2a8ff;--line:#30363d}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);
font-family:ui-sans-serif,system-ui,"Segoe UI",Roboto,sans-serif}
#app{display:flex;height:100vh;overflow:hidden}
/* 侧栏 */
#side{width:320px;min-width:300px;border-right:1px solid var(--border);display:flex;flex-direction:column;background:var(--panel)}
#q{margin:10px;padding:8px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--fg);font-size:13px}
#tree{flex:1;overflow:auto;padding:4px 8px 40px}
.gtitle{font-size:11px;letter-spacing:.12em;color:var(--muted);text-transform:uppercase;margin:12px 6px 4px}
.fitem{display:flex;gap:8px;align-items:center;padding:5px 8px;border-radius:6px;cursor:pointer;font-size:13px;color:var(--fg);white-space:nowrap}
.fitem:hover{background:#21262d}
.fitem.on{background:rgba(88,166,255,.15);color:var(--accent)}
.fitem .ln{margin-left:auto;color:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.mark{background:var(--warn);color:#111;border-radius:2px}
/* 主区 */
#main{flex:1;overflow:auto;padding:0}
.hbtns{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--border);padding:10px 18px;display:flex;gap:10px;align-items:center}
.hbtns h1{font-size:15px;font-weight:600;margin:0 0 0 auto;color:var(--fg)}
button.b{background:#21262d;border:1px solid var(--border);color:var(--fg);padding:5px 12px;border-radius:6px;cursor:pointer;font-size:12px}
button.b:hover{border-color:var(--accent)}
body.light{--bg:#f6f8fa;--panel:#ffffff;--border:#d0d7de;--fg:#1f2328;--muted:#57606a;
--code:#1f2328;--kw:#cf222e;--str:#0a3069;--com:#57606a;--num:#0550ae;--fn:#8250df;--line:#eaeef2}
#stage{padding:14px 18px 60px}
pre.code{margin:0;background:var(--bg);border:1px solid var(--border);border-radius:8px;overflow:auto;padding:14px 0;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.row{display:flex}
.ln{width:54px;min-width:54px;text-align:right;padding:0 10px;color:var(--muted);user-select:none;font:13px/1.55 ui-monospace,Menlo,Consolas,monospace}
.cs{padding:0 14px 0 0;white-space:pre;font:13px/1.55 ui-monospace,Menlo,Consolas,monospace;color:var(--code)}
.kw{color:var(--kw)} .st{color:var(--str)} .cm{color:var(--com)} .nm{color:var(--num)} .fn{color:var(--fn)}
#path{font:12px ui-monospace,Menlo,Consolas,monospace;color:var(--muted);margin:0 2px}
#hint{color:var(--muted);font-size:13px;padding:40px;text-align:center}
@media (max-width:860px){#side{width:240px;min-width:220px}}
</style>
</head>
<body>
<div id="app">
 <aside id="side">
  <input id="q" type="search" placeholder="搜索代码（支持 Ctrl+F 焦点）" autocomplete="off">
  <div id="tree"></div>
 </aside>
 <main id="main">
  <div class="hbtns">
    <button class="b" id="expand">全部展开</button>
    <button class="b" id="collapse">全部折叠</button>
    <button class="b" id="theme">切换主题</button>
    <span id="path"></span>
    <h1>ai-content-hub · 完整代码查看器</h1>
  </div>
  <div id="stage"><div id="hint">从左侧选择一个文件查看完整代码</div></div>
 </main>
</div>
<script>
const DATA=__PAYLOAD__;
const GROUPS=DATA.groups, FILES=DATA.files;
const state={open:new Set(FILES.map(f=>f.path)), lang:false, cur:FILES[0].path};
const $=s=>document.querySelector(s);
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function hl(src){
  let out='';const lines=src.split('\n');
  for(let ln of lines){
    let h=esc(ln);
    // 注释 // # /* */
    h=h.replace(/(\/\*[\s\S]*?\*\/|\/\/.*$|#.*$)/g,'<span class="cm">$1</span>');
    // 字符串（单/双/反引号）
    h=h.replace(/(`(?:\\.|[^`\\])*`|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g,'<span class="st">$1</span>');
    // 数字
    h=h.replace(/\b(\d+\.?\d*)\b/g,'<span class="nm">$1</span>');
    // 关键字
    h=h.replace(/\b(function|return|const|let|var|if|else|for|while|import|from|export|def|class|try|except|finally|raise|with|as|pass|lambda|self|None|True|False|async|await|new|this|null|undefined|def|elif|in|is|not|and|or|raise|None|True|False)\b/g,'<span class="kw">$1</span>');
    out+='\n'+h;
  }
  return out.slice(1);
}
function renderTree(){
  const q=$('#q').value.trim().toLowerCase();
  let h='';
  for(const g of GROUPS){
    const fs=FILES.filter(f=>f.group===g && (!q||f.path.toLowerCase().includes(q)||f.src.toLowerCase().includes(q)));
    if(!fs.length) continue;
    h+='<div class="gtitle">'+g+'</div>';
    for(const f of fs){
      h+='<div class="fitem" data-p="'+f.path+'"><span>'+f.path+'</span><span class="ln">'+f.lines+'</span></div>';
    }
  }
  $('#tree').innerHTML=h||'<div class="gtitle">无匹配</div>';
  $('#tree').querySelectorAll('.fitem').forEach(el=>{
    el.onclick=()=>openFile(el.dataset.p);
    if(el.dataset.p===state.cur) el.classList.add('on');
  });
}
function openFile(p){
  state.cur=p;
  const f=FILES.find(x=>x.path===p); if(!f)return;
  const open=state.open.has(p);
  const lines=f.src.split('\n');
  let body='';
  const show=open?lines.length:Math.min(lines.length,1);
  for(let i=0;i<show;i++){
    const t=lines[i]===''?' ':lines[i];
    body+='<div class="row"><div class="ln">'+(i+1)+'</div><div class="cs">'+hl(lines[i])+'</div></div>';
  }
  const hasMore=open?'':'<div class="fitem" style="margin:6px 0" id="more"><span>展开全部（'+lines.length+' 行）</span></div>';
  $('#stage').innerHTML='<pre class="code" id="pre">'+body+'</pre>'+ (open? hasMore:'');
  if(!open){const m=$('#more'); if(m) m.onclick=()=>{state.open.add(p);openFile(p);};}
  const pre=$('#pre');
  if(!open){ pre.style.maxHeight='220px'; pre.style.overflow='hidden'; pre.style.transition='max-height .25s';
    requestAnimationFrame(()=>{pre.style.maxHeight=(lines.length*22+200)+'px';}); }
  else { pre.style.maxHeight='none'; }
  $('#path').textContent=p+'  ·  '+lines.length+' 行';
  renderTree();
}
function allExpand(){FILES.forEach(f=>state.open.add(f.path));openFile(state.cur);}
function allCollapse(){FILES.forEach(f=>state.open.delete(f.path));openFile(state.cur);}
$('#expand').onclick=allExpand;
$('#collapse').onclick=allCollapse;
$('#theme').onclick=()=>document.body.classList.toggle('light');
$('#q').oninput=renderTree;
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='f'){e.preventDefault();$('#q').focus();}});
renderTree();
openFile(FILES[0].path);
</script>
</body>
</html>
"""


out = TEMPLATE.replace("__PAYLOAD__", payload)
dst = ROOT / "code-explorer.html"
dst.write_text(out, encoding="utf-8")
total = sum(f["lines"] for f in data)
print("OK", dst, "files=", len(data), "total_lines=", total)
