# -*- coding: utf-8 -*-
"""发布工作流的状态模型（接口契约）。

字段名是跨节点/runner/API 的硬契约，逐字一致，改名必须同步
ARCHITECTURE.md §3.3 与所有节点。

语义说明：
  普通字段    —— 覆盖语义（后写的节点覆盖先写的）
  Annotated  —— 追加语义（operator.add，各节点只追加自己的条目）
"""
import operator
from typing import Annotated, TypedDict


class PublishState(TypedDict, total=False):
    # —— 运行标识与入参 ——
    run_id: str                # workflow_runs.id
    article_id: int
    account: str
    draft_only: bool
    dry_run: bool              # 预演模式：不触真实平台，合成结果（ADR-005）

    # —— 编排游标 ——
    platforms_queue: list      # 待发平台队列（next_platform 弹出）
    current_platform: str      # 当前平台（'' = 队列已空）
    attempts: int              # 当前平台已尝试次数（publish_platform 递增）

    # —— 中间产物 ——
    article: dict              # 载入/闸门修正后的文章
    gate: dict                 # 闸门结果 {'passed': bool, ...}
    current_result: dict       # 当前平台最近一次尝试结果（覆盖语义）

    # —— 累积产物（追加语义） ——
    results: Annotated[list, operator.add]     # 每平台终态（含 platform/ok/status/...）
    decisions: Annotated[list, operator.add]   # 分诊决策留痕（审计用）

    # —— 异常与收尾 ——
    fatal: str                 # 引擎级终止原因（文章缺失/门禁拒绝）
    human_resume: dict         # wait_human 恢复时人的输入 {'approved','note'}
    wait_action: str           # wait_human 恢复后的去向: publish|verify|next（路由契约）
    summary: dict              # aggregate 汇总（runner 落库 result_json.summary）


class UpdateState(TypedDict, total=False):
    """原地更新工作流状态（M5/ADR-007，规格=docs/design/m5-architecture.md §4.2 逐字）。

    契约规则（§4.3）：与 PublishState 同名的字段必须同义同型（reducer 一致）；
    任一侧改名必须同步 ARCHITECTURE §3.3/§3.5 与全部节点。
    wait_action 取值集合统一 publish|verify|next（update 图中 verify 不可达但取值保留）。
    """

    # —— 运行标识与入参（与 PublishState 同名同义） ——
    run_id: str                 # workflow_runs.id
    article_id: int
    account: str
    dry_run: bool               # 预演模式：不触真实平台，合成结果（ADR-005 语义沿用）

    # —— 编排游标 ——
    platforms_queue: list       # 待更新平台队列（next_target 弹出；start() 按目标实例建队）
    current_platform: str       # 当前平台（'' = 队列已空）
    current_pub: dict           # 当前平台的发布实例行 {platform, post_id, edit_url, account}
    target_pubs: dict           # platform → 实例行（start() 一次性写入，next_target 查表用）
    attempts: int               # 当前平台已尝试次数（update_instance 递增）

    # —— 中间产物 ——
    article: dict               # 载入并经闸门修正后的文章
    gate: dict                  # 闸门结果 {'passed': bool, ...}
    current_result: dict        # 当前平台最近一次尝试结果（覆盖语义）

    # —— 累积产物（追加语义，与 PublishState 同款 reducer） ——
    results: Annotated[list, operator.add]
    decisions: Annotated[list, operator.add]

    # —— 异常与收尾 ——
    fatal: str                  # 引擎级终止原因（文章缺失/标题为空/闸门拒绝）
    human_resume: dict          # wait_human 恢复时人的输入 {'approved', 'note'}
    wait_action: str            # wait_human 恢复去向: publish|next（verify 本图不可达）
    summary: dict               # aggregate_update 收敛（runner 落库 result_json.summary）
