# -*- coding: utf-8 -*-
"""发布工作流节点实现。

两类节点（ADR-002：编排为主，关键决策交 LLM）：
  确定性节点  load_article / compliance_gate / next_platform / ensure_login /
              publish_platform / verify_publish / wait_human / aggregate
              —— 复用 Hub 与适配器，行为与 legacy publish 保持一致
  LLM 决策节点 triage —— 失败分诊（retry/human/skip），heuristic 兜底

失败分诊优先级：heuristic 命中（配置类→skip / 风控类→human / 瞬时类→retry）
→ LLM 终审（重试额度用尽或无明显归类时）→ 兜底 skip。
"""
import json
import random
import time
from pathlib import Path

from langgraph.types import interrupt

from core import db
from core import gate as aigc_gate
from core.ai import chat as ai_chat, is_ready as ai_is_ready
from core.adapters.base import PlatformError, get_adapter

ROOT = Path(__file__).resolve().parent.parent

# 错误归类词典（heuristic 分诊依据，与 LLM 分诊互补）
CREDENTIAL_TOKENS = ('未登录', '凭据', 'token', 'config', 'api_key',
                     '不支持的平台', '先跑 login')
RISK_TOKENS = ('验证码', 'captcha', '风控', '滑块', '限流')
RETRYABLE_TOKENS = ('timeout', '超时', 'target closed', 'session closed',
                    'connection', '网络', '500', '502', '503', '504', 'temporary')

TRIAGE_SYSTEM = """你是发布管线的失败分诊器。根据平台与错误信息，从三个动作里选一个：
retry=瞬时错误值得再试；human=需要人处理（登录/风控/平台后台操作）；skip=自动重试无意义。
只输出一行 JSON：{"action": "retry|human|skip", "reason": "一句话理由"}"""


def _retry_limit():
    """config.json workflow.retry_limit，默认 2。"""
    try:
        cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
        return int((cfg.get('workflow') or {}).get('retry_limit', 2))
    except Exception:
        return 2


def _llm_triage(state, pf, err, attempts, limit):
    """LLM 分诊。返回 (action, reason)；解析失败抛异常由调用方兜底。"""
    payload = {
        'platform': pf, 'attempts': attempts, 'retry_limit': limit,
        'draft_only': bool(state.get('draft_only')),
        'dry_run': bool(state.get('dry_run')),
        'error': (err or '')[:400],
        'article_title': (state.get('article') or {}).get('title', ''),
    }
    raw = ai_chat([{'role': 'system', 'content': TRIAGE_SYSTEM},
                   {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                  temperature=0, max_tokens=120)
    m = json.loads(raw[raw.find('{'): raw.rfind('}') + 1])
    return str(m.get('action', '')), str(m.get('reason', ''))[:120]


def _decide(state, pf, err, attempts, limit):
    """分诊决策。返回 (action, reason, by)。"""
    e = (err or '').lower()
    if any(t in e for t in CREDENTIAL_TOKENS):
        return 'skip', '登录/配置类错误，自动化重试无意义', 'heuristic'
    if any(t in e for t in RISK_TOKENS):
        return 'human', '触发风控/验证码，需人工处理', 'heuristic'
    if attempts < limit and any(t in e for t in RETRYABLE_TOKENS):
        return 'retry', f'瞬时性错误，进行第 {attempts + 1} 次重试', 'heuristic'
    if ai_is_ready():
        try:
            action, reason = _llm_triage(state, pf, err, attempts, limit)
            if action == 'retry' and attempts >= limit:
                return 'skip', '重试额度已用尽（LLM 建议重试被上限拦截）'
            if action in ('retry', 'human', 'skip'):
                return action, reason or '(LLM 未给理由)', 'llm'
        except Exception:
            pass  # LLM 不可用/解析失败 → heuristic 兜底
    return 'skip', '未知错误，保守跳过（可人工重发）', 'heuristic'


def build_nodes(hub):
    """节点工厂：闭包注入 Hub（浏览器池/DB/AI 全在 hub 上）。"""

    # ---------------- 确定性节点 ----------------

    def load_article(state):
        art = hub.get(state['article_id'])
        if not art:
            return {'fatal': f'文章 {state["article_id"]} 不存在'}
        if not (art.get('title') or '').strip():
            return {'article': art, 'fatal': '文章标题为空，拒绝发布（B19 预检）'}
        return {'article': art}

    def compliance_gate(state):
        if state.get('dry_run'):
            return {'gate': {'passed': True, 'dry_run': True}}
        try:
            res = aigc_gate.apply_gate_before_publish(
                state['article'], draft_only=bool(state.get('draft_only')))
        except aigc_gate.GateError as ge:
            return {'fatal': f'合规门禁拒绝发布: {ge}'}
        # 契约：apply_gate_before_publish 返回 {'result': {...}, 'article': {...}}
        return {'article': res['article'],
                'gate': {'passed': True,
                         'aigc_labeled': res['result'].get('aigc_labeled', False)}}

    def next_platform(state):
        q = list(state.get('platforms_queue') or [])
        if not q:
            return {'current_platform': ''}
        return {'platforms_queue': q[1:], 'current_platform': q[0],
                'attempts': 0, 'current_result': {}}

    def ensure_login(state):
        """平台合法性预检（登录态由 publish_platform 内部 _with_adapter 把关，
        这里不重复开浏览器；M2 在此挂自动登录/人工升级钩子）。"""
        pf = state.get('current_platform', '')
        try:
            get_adapter(pf)
        except PlatformError as e:
            return {'current_result': {'platform': pf, 'ok': False, 'error': str(e)}}
        return {'current_result': {'platform': pf, 'ok': True, 'phase': 'precheck'}}

    def publish_platform(state):
        pf = state['current_platform']
        attempts = int(state.get('attempts') or 0) + 1
        if state.get('dry_run'):
            time.sleep(0.2)   # 模拟真实节奏，验证状态机
            return {'attempts': attempts, 'current_result': {
                'platform': pf, 'ok': True, 'dry_run': True, 'status': 'ok',
                'post_id': f'dry-{random.randint(10**11, 10**12 - 1)}',
                'post_url': '', 'edit_url': ''}}
        try:
            r = hub.publish_single(state['article_id'], pf, state['article'],
                                   account=state.get('account', 'default'),
                                   draft_only=bool(state.get('draft_only')))
            return {'attempts': attempts, 'current_result': {**r, 'ok': True}}
        except Exception as e:
            return {'attempts': attempts, 'current_result': {
                'platform': pf, 'ok': False, 'error': str(e)[:300]}}

    def verify_publish(state):
        """发布后验证：GET post_url 看可达性 + 标题命中。
        只做观测记录（verify 字段），不翻转 ok —— 平台反爬页/渲染差异不算失败。"""
        cur = dict(state.get('current_result') or {})
        if state.get('dry_run') or state.get('draft_only') or not cur.get('post_url'):
            cur['verify'] = 'skipped'
            return {'current_result': cur}
        try:
            import requests
            resp = requests.get(cur['post_url'], timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'})
            title = (state.get('article') or {}).get('title', '')
            hit = bool(title) and title[:24] in resp.text
            if resp.status_code == 200:
                cur['verify'] = 'ok' if hit else 'reachable'
            else:
                cur['verify'] = f'http-{resp.status_code}'
        except Exception as e:
            cur['verify'] = f'unverified: {str(e)[:80]}'
        return {'current_result': cur}

    def wait_human(state):
        """人机协作挂起点（ADR-001 interrupt 原语），两种场景：
        - draft_confirm：发布回落草稿（cur.status=pending_human），人工去平台
          点完「确定并发布」回来确认 → 翻转发布实例 pending_human→ok → 去 verify
        - recover：发布失败转人工（验证码/登录），人工排除故障回来 →
          回 publish_platform 重新尝试（attempts 归零，人背书新一轮）

        首次进入：interrupt() 抛出挂起，payload 存 checkpoint；
        恢复进入：interrupt() 返回人的输入（{'approved': bool, 'note': str}）。
        路由契约：返回 wait_action ∈ publish|verify|next（见 graph._route_after_wait）。"""
        cur = dict(state.get('current_result') or {})
        pf = cur.get('platform', state.get('current_platform', ''))
        case = 'draft_confirm' if cur.get('status') == 'pending_human' else 'recover'
        payload = {
            'run_id': state.get('run_id'), 'article_id': state.get('article_id'),
            'title': (state.get('article') or {}).get('title', ''),
            'platform': pf, 'post_id': cur.get('post_id', ''),
            'edit_url': cur.get('edit_url', ''), 'error': cur.get('error', ''),
            'attempts': state.get('attempts', 0), 'case': case,
            'message': ('草稿已就位：到平台点「确定并发布」，完成后回来点「已处理，恢复」'
                        if case == 'draft_confirm' else
                        f'{pf} 发布被拦（{str(cur.get("error", ""))[:60]}），'
                        '人工排除故障后回来点「已处理，恢复」重试'),
        }
        answer = interrupt(payload)
        ans = answer if isinstance(answer, dict) else {}
        note = str(ans.get('note', ''))[:200]
        if not ans.get('approved'):
            if case == 'draft_confirm':
                # 草稿真实存在于平台，维持 pending_human——/pending-human 队列继续提醒
                return {'human_resume': ans, 'wait_action': 'next',
                        'results': [{**cur, 'note': note or '人工暂不确认，草稿保持待发布'}]}
            return {'human_resume': ans, 'wait_action': 'next',
                    'results': [{**cur, 'status': 'failed',
                                 'note': note or '人工放弃'}]}
        if case == 'draft_confirm':
            # 人在平台完成最后一步 → 发布实例翻转为已发布（pending_human→ok）
            try:
                hub.conn.execute(
                    """UPDATE publications SET status='ok', draft_only=0, last_error='',
                       updated_at=? WHERE article_id=? AND platform=?
                       AND status='pending_human'""",
                    (db.now(), state.get('article_id'), pf))
                hub.conn.commit()
            except Exception:
                pass  # 翻转失败不阻塞 run，发布实例状态可事后对账
            cur = {k: v for k, v in cur.items() if k != 'error'}
            cur = {**cur, 'ok': True, 'status': 'ok',
                   'note': note or '人工已在平台完成发布'}
            return {'human_resume': ans, 'wait_action': 'verify',
                    'current_result': cur}
        # recover：故障已排除，attempts 归零回发布节点（人背书新一轮重试）
        return {'human_resume': ans, 'wait_action': 'publish', 'attempts': 0,
                'current_result': {'platform': pf, 'ok': False, 'error': ''}}

    def aggregate(state):
        results = list(state.get('results') or [])
        fatal = state.get('fatal', '')
        dry = bool(state.get('dry_run'))
        draft = bool(state.get('draft_only'))
        all_ok = bool(results) and all(r.get('ok') for r in results) \
            and not any(r.get('status') == 'pending_human' for r in results)
        # 文章状态收敛（与 legacy publish 语义一致）
        if not fatal and not dry and not draft and all_ok:
            try:
                db.update_article(hub.conn, state['article_id'], status='published')
            except Exception:
                pass
        summary = {
            'fatal': fatal, 'dry_run': dry, 'draft_only': draft,
            'platforms_total': len(results),
            'platforms_ok': sum(1 for r in results if r.get('ok')),
            'ok': bool(not fatal and all_ok),
            'pending_human': [r.get('platform') for r in results
                              if r.get('status') == 'pending_human'],
            'failed': [{'platform': r.get('platform'),
                        'error': (r.get('error') or '')[:160]}
                       for r in results if not r.get('ok')],
        }
        return {'summary': summary}

    # ---------------- LLM 决策节点 ----------------

    def triage(state):
        cur = dict(state.get('current_result') or {})
        pf = cur.get('platform', state.get('current_platform', ''))
        queue_left = list(state.get('platforms_queue') or [])
        dry = bool(state.get('dry_run'))

        def finish(result):
            # 平台收尾：非末平台按风控间隔让一让（legacy 同款，dry_run 不睡）
            if not dry and queue_left:
                time.sleep(random.uniform(*hub.delay_platform))
            return {'results': [result]}

        if cur.get('ok'):
            # 草稿收尾差人工一步（如掘金回落草稿）→ 不落结果，路由到 wait_human 挂起
            if cur.get('status') == 'pending_human' or cur.get('pending_human'):
                return {}
            return finish({**cur, 'status': cur.get('status', 'ok'),
                           'attempts': int(state.get('attempts') or 0)})

        err = cur.get('error', '')
        attempts = int(state.get('attempts') or 0)
        limit = _retry_limit()
        action, reason, by = _decide(state, pf, err, attempts, limit)
        decision = {'platform': pf, 'error': err[:160], 'attempts': attempts,
                    'action': action, 'reason': reason, 'by': by, 'ts': time.time()}
        if action == 'retry':
            time.sleep(0.2 if dry else min(8 * attempts, 24))
            return {'decisions': [decision]}          # 回边 → publish_platform
        if action == 'human':
            return {'decisions': [decision]}          # → wait_human
        return {**finish({**cur, 'status': 'failed'}), 'decisions': [decision]}

    return {
        'load_article': load_article,
        'compliance_gate': compliance_gate,
        'next_platform': next_platform,
        'ensure_login': ensure_login,
        'publish_platform': publish_platform,
        'verify_publish': verify_publish,
        'wait_human': wait_human,
        'triage': triage,
        'aggregate': aggregate,
    }
