# checkpoint-3 · Phase 3（实现）定稿基线

## 目标
M5 切流实现完成且冒烟全绿（R1/R3 合并门禁通过）后的版本基线；之后进入 Phase 4（工程化）。

## 产出物
- workflows/：UpdateState + build_update_nodes + build_update_graph + runner kind 泛化（双图字典/幂等迁移/autocommit）
- core/service.py：Hub.update_single 抽取（legacy update() 逐行搬移，双跑 DB 对账一致）
- server/api.py：POST /articles/{aid}/update/workflow、POST /sync/pending/workflow、/runs kind/article_id 过滤、legacy 端点 strangler 注记
- server/mcp_server.py：update_article/sync_pending 切流（900s deadline，仅启动失败回退）
- scripts/smoke_update.py：S1–S5 + S6 双跑对账（六案全绿）
- docs/design/m5-{architecture,api,data}.md + docs/design/tech-debt.md + ARCHITECTURE/AUDIT 回写

## 关键决策
1. ADR-007/008/009（update 专图、sync 扇出、update 门禁豁免层4）——详见 docs/design/m5-architecture.md §8
2. D-C（sync 响应 failed[]）经主理人中转获批并回写架构底稿 §6.1
3. 实施期修复三缺陷：update_instance 缺出边（S1 首跑实锤）、_route_after_login 令牌跨图不匹配、S5 并行 commit 竞态（autocommit）

## 回滚指令
```bash
# 回到本检查点之后的状态回退：
git reset --hard phase-3
# 更保守（仅撤代码、保留设计文档）：
git checkout phase-2 -- core/ server/ workflows/ scripts/
# 运行时回退（不回滚代码）：config.json 设 "workflow": {"enabled": false} 或客户端改走 legacy 端点
```
