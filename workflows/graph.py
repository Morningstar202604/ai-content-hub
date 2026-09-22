# -*- coding: utf-8 -*-
"""发布工作流图构建（拓扑见 ARCHITECTURE.md §3.1）。

START → load_article → compliance_gate → next_platform ⇄(平台循环)
        ensure_login → publish_platform → verify_publish → triage
          triage ─ retry → publish_platform（有界回边，上限 workflow.retry_limit）
          triage ─ human  → wait_human(interrupt) →(恢复)→ verify_publish
          triage ─ skip/done → next_platform
        队列空 → aggregate → END
"""
from langgraph.graph import StateGraph, START, END

from workflows.nodes import build_nodes
from workflows.state import PublishState


def _route_after_load(s):
    return 'aggregate' if s.get('fatal') else 'gate'


def _route_after_gate(s):
    return 'aggregate' if s.get('fatal') else 'next'


def _route_after_next(s):
    return 'login' if s.get('current_platform') else 'aggregate'


def _route_after_login(s):
    # 预检失败（未知平台等）→ 直接进分诊记失败；正常 → 发布
    return 'triage' if not (s.get('current_result') or {}).get('ok') else 'publish'


def _route_after_triage(s):
    cur = s.get('current_result') or {}
    if cur.get('ok'):
        # 草稿收尾差人工一步 → 挂起等确认（draft_confirm 场景，triage 未落结果）
        if cur.get('status') == 'pending_human' or cur.get('pending_human'):
            return 'wait_human'
        return 'next'
    action = ((s.get('decisions') or [{}])[-1] or {}).get('action')
    if action == 'retry':
        return 'publish'
    if action == 'human':
        return 'wait_human'
    return 'next'


def _route_after_wait(s):
    # 恢复动作三向分发（节点契约 wait_action）：
    #   publish=故障已排除回发布节点重试 / verify=草稿已发布去验证 / next=放弃本平台
    return {'publish': 'publish', 'verify': 'verify',
            'next': 'next'}.get(s.get('wait_action') or 'next', 'next')


def build_graph(hub, checkpointer=None):
    """构建并编译发布工作流图。checkpointer 由 runner 注入（SqliteSaver）。"""
    n = build_nodes(hub)
    g = StateGraph(PublishState)
    g.add_node('load_article', n['load_article'])
    g.add_node('compliance_gate', n['compliance_gate'])
    g.add_node('next_platform', n['next_platform'])
    g.add_node('ensure_login', n['ensure_login'])
    g.add_node('publish_platform', n['publish_platform'])
    g.add_node('verify_publish', n['verify_publish'])
    g.add_node('wait_human', n['wait_human'])
    g.add_node('triage', n['triage'])
    g.add_node('aggregate', n['aggregate'])

    g.add_edge(START, 'load_article')
    g.add_conditional_edges('load_article', _route_after_load,
                            {'gate': 'compliance_gate', 'aggregate': 'aggregate'})
    g.add_conditional_edges('compliance_gate', _route_after_gate,
                            {'next': 'next_platform', 'aggregate': 'aggregate'})
    g.add_conditional_edges('next_platform', _route_after_next,
                            {'login': 'ensure_login', 'aggregate': 'aggregate'})
    g.add_conditional_edges('ensure_login', _route_after_login,
                            {'publish': 'publish_platform', 'triage': 'triage'})
    g.add_edge('publish_platform', 'verify_publish')
    g.add_edge('verify_publish', 'triage')
    g.add_conditional_edges('triage', _route_after_triage,
                            {'publish': 'publish_platform',
                             'wait_human': 'wait_human',
                             'next': 'next_platform'})
    g.add_conditional_edges('wait_human', _route_after_wait,
                            {'publish': 'publish_platform',
                             'verify': 'verify_publish',
                             'next': 'next_platform'})
    g.add_edge('aggregate', END)
    return g.compile(checkpointer=checkpointer)
