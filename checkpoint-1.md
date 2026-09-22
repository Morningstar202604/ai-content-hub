# Checkpoint 1 — Phase 1 基线检查点

> 日期：2026-09-22 · 分支：main · tag：`phase-1`
> 本文件所在提交即 Phase 1 检查点（M1–M4 + 全量审计修复落库）。

## 1. 目标

把工作区中未提交的 M1–M4 实施成果与 AUDIT 全量检测修复固化为一个基线提交，打 tag `phase-1`，
形成可随时回退的 Phase 1 检查点；同时确认凭据与登录资产绝不入库。

## 2. 产出物

| 项 | 值 |
|---|---|
| 基线提交 | 本 commit（可用 `git rev-parse phase-1` 查看完整 hash） |
| Tag | `phase-1`（轻量 tag，指向本提交） |
| 本文件 | `checkpoint-1.md`（仓库根） |
| 覆盖范围 | M1 工作流引擎（workflows/）· M2 人机协作 · M3 LLM 分诊 · M4 治理归档（scripts/）· AUDIT 12 项修复 · ARCHITECTURE.md / AUDIT.md 文档 |

## 3. 关键决策

1. **单提交落库**：M1–M4+审计修复体量大但属同一阶段成果，合并为一个 commit，回退粒度干净（一次 `reset` 回到阶段前）。
2. **.gitignore 只增不删**：在既有 `config.json` / `.env` / `data/` 规则基础上补 `*.auth.json`，覆盖任意路径的登录快照；已用 `git check-ignore` 验证 config.json、.env、data/profiles/*.auth.json、data/*.db 全部命中，且 `git ls-files` 确认无凭据文件被跟踪。
3. **不动业务文件语义**：仅执行 add/commit/tag/新增 md，不 push 任何远端；git 身份仅做仓库级（--local）设置（若原本缺失）。

## 4. 回滚指令（可直接复制执行）

```bash
# ① 回到本检查点（丢弃检查点之后的所有提交，工作区对齐 phase-1）
git checkout main
git reset --hard phase-1

# ② 仅回滚某文件到本检查点版本
git checkout phase-1 -- <路径>

# ③ 删除本 tag（确认不再需要该检查点时）
git tag -d phase-1

# ④ 查看本检查点信息
git show phase-1 --stat
git rev-parse phase-1
```

> 注意：`reset --hard` 会丢弃检查点之后的提交与工作区未提交改动，执行前先 `git stash` 或确认无需保留。
