# checkpoint-2 · Phase 2（数据与接口）定稿基线

## 目标
Phase 2 三份设计产物定稿入库，作为 Phase 3（backend 实现，本检查点之后第一个改代码的阶段）启动前的回滚点。

## 产出物
- docs/design/m5-architecture.md（architect：三裁定/图拓扑/UpdateState/ADR-007~009/实施七步）
- docs/design/m5-api.md（api-designer：5 端点字段级契约/OpenAPI/兼容矩阵/B1–B12 边界表）
- docs/design/tech-debt.md（tech-debt-strategist：12 债台账/T1–T3 排期/两轮修订后的 T3 卡口）
- docs/design/m5-data.md（主理人补位：workflow_runs kind 列幂等迁移规范——database-engineer 因 429 缺位）

## 关键决策
1. ADR-007：update 独立图 + 独立 UpdateState + runner kind 路由（PublishState/publish 图零改动，回退解耦）
2. ADR-008：sync_pending 编排层一文一 run 扇出；refresh 永久 legacy（重评触发条件已写死）
3. ADR-009：update 合规门禁 `draft_only=True` 豁免层4、保留层1+层3（堵 ai_rewrite→sync 高危词直推缺口）
4. D-C（经主理人中转，architect 签批）：sync 响应 additive `failed[]`
5. T3 卡口：⓪ update_single 抽取（0.5d，R3 源）未验完不开工①切流；③ strangler 注记必须等 S1–S6 冒烟全绿

## 回滚指令
```bash
# 回到本检查点（丢弃其后的全部代码改动；本检查点之后才允许动代码）
git reset --hard phase-2
# 仅撤销标签（保留工作区）：
git tag -d phase-2
```
