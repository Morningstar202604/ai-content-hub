<template>
  <div class="pane manage">
    <div class="pane-head">
      <span class="title">发布管理</span>
      <span class="spacer" />
      <el-button size="small" text :icon="Refresh" :loading="reloading" @click="reloadAll">刷新全部</el-button>
    </div>

    <div class="pane-body">
      <el-tabs v-model="tab">
        <!-- 需要人工 -->
        <el-tab-pane name="human">
          <template #label>
            需要人工
            <el-badge v-if="hub.pendingHuman.length + hub.waitingRuns.length"
                      :value="hub.pendingHuman.length + hub.waitingRuns.length"
                      type="warning" class="tab-badge" />
          </template>

          <!-- 工作流挂起的 run（引擎 interrupt 产物，带恢复按钮） -->
          <div v-if="hub.waitingRuns.length" class="human-grid">
            <div v-for="r in hub.waitingRuns" :key="r.id" class="human-card run-card">
              <div class="hc-head">
                <el-tag size="small" type="danger" effect="dark">工作流挂起</el-tag>
                <el-tag size="small" effect="plain">{{ r.human_task?.platform || '?' }}</el-tag>
                <span class="hc-title">{{ r.title || '未命名文章' }}</span>
              </div>
              <div class="hc-sub">
                {{ r.human_task?.message || '工作流已挂起，等待人工处理' }}
                <div v-if="r.human_task?.error" class="hc-err">{{ r.human_task.error }}</div>
              </div>
              <div class="hc-ops">
                <el-button v-if="r.human_task?.edit_url" size="small" type="warning"
                           @click="goUrl(r.human_task.edit_url)">打开平台页面</el-button>
                <el-button size="small" type="primary"
                           :loading="resuming === r.id"
                           @click="doResume(r, true)">已处理，恢复</el-button>
                <el-button size="small" text @click="doResume(r, false)">放弃</el-button>
                <el-button size="small" text @click="showRun(r)">详情</el-button>
              </div>
            </div>
          </div>

          <!-- legacy 发布实例 pending_human（旧路径产物） -->
          <div v-if="hub.pendingHuman.length" class="human-grid" style="margin-top:12px">
            <div v-for="it in hub.pendingHuman" :key="it.platform + it.article_id" class="human-card">
              <div class="hc-head">
                <el-tag size="small" type="warning" effect="dark">{{ it.platform }}</el-tag>
                <span class="hc-title">{{ it.title || '未命名文章' }}</span>
              </div>
              <div class="hc-sub">自动化已完成到草稿，差最后一步人工发布（登录后点「确定并发布」）</div>
              <div class="hc-ops">
                <el-button size="small" type="warning" @click="goHandle(it)">打开草稿去发布</el-button>
                <el-button size="small" text @click="hub.loadPendingHuman()">我处理完了，刷新</el-button>
              </div>
            </div>
          </div>
          <EmptyState v-if="!hub.pendingHuman.length && !hub.waitingRuns.length"
                      title="没有等待人工的任务"
                      desc="全自动发布顺利时这里一直是空的；掘金等平台需要人工收尾或引擎挂起时会出现在这里"
                      :px="72" />
        </el-tab-pane>

        <!-- 运行记录（工作流 run 全史 + 分诊决策审计） -->
        <el-tab-pane label="运行记录" name="runs">
          <el-table v-if="hub.runs.length" :data="hub.runs" size="default" max-height="620"
                    @row-click="showRun" row-style="cursor:pointer">
            <el-table-column label="Run" width="120">
              <template #default="{ row }"><span class="dim">{{ row.id }}</span></template>
            </el-table-column>
            <el-table-column label="文章" min-width="200">
              <template #default="{ row }">{{ row.title || ('#' + row.article_id) }}</template>
            </el-table-column>
            <el-table-column label="平台" width="130">
              <template #default="{ row }">{{ (row.platforms || []).join('、') }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="runTagType(row.status)" effect="dark">
                  {{ runTagText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="结果" min-width="150">
              <template #default="{ row }">
                <span v-if="row.summary" class="dim">
                  {{ row.summary.platforms_ok ?? 0 }}/{{ row.summary.platforms_total ?? 0 }} 成功
                  <template v-if="row.summary.pending_human?.length">
                    · 待人工 {{ row.summary.pending_human.join('、') }}
                  </template>
                </span>
                <span v-else-if="row.error" class="run-err">{{ row.error.slice(0, 40) }}</span>
                <span v-else class="dim">—</span>
              </template>
            </el-table-column>
            <el-table-column label="时间" width="150">
              <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="还没有工作流运行" desc="用发布向导发一篇，或调 /publish/workflow 接口" :px="96" />
        </el-tab-pane>

        <!-- 发布记录 -->
        <el-tab-pane label="发布记录" name="pubs">
          <el-table v-if="hub.allPubs.length" :data="hub.allPubs" size="default" max-height="620">
            <el-table-column label="文章" min-width="220">
              <template #default="{ row }">
                <span class="p-title">{{ row.title || ('#' + row.article_id) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="平台" width="90">
              <template #default="{ row }">{{ row.platform }}</template>
            </el-table-column>
            <el-table-column label="状态" width="96">
              <template #default="{ row }">
                <el-tag size="small" :type="tagType(row.status)" effect="dark">{{ tagText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="链接" min-width="160">
              <template #default="{ row }">
                <a v-if="row.post_url" class="p-link" :href="row.post_url" target="_blank" rel="noopener">打开文章</a>
                <a v-else-if="row.edit_url" class="p-link" :href="row.edit_url" target="_blank" rel="noopener">打开编辑页</a>
                <span v-else class="dim">—</span>
              </template>
            </el-table-column>
            <el-table-column label="时间" width="150">
              <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="还没有发布记录" :px="96" />
        </el-tab-pane>

        <!-- 平台与账号 -->
        <el-tab-pane label="平台与账号" name="accounts">
          <div class="acct-grid">
            <div v-for="p in hub.platforms" :key="p.id" class="acct-card">
              <div class="ac-top">
                <b class="ac-name">{{ p.name }}</b>
                <el-tag size="small" :type="acctState(p.id) ? 'success' : 'info'" effect="dark">
                  {{ acctState(p.id) ? '在线' : '离线' }}
                </el-tag>
              </div>
              <div class="ac-sub">{{ p.needs_browser ? '需要浏览器登录（扫码一次长期有效）' : '免登 API，凭据在 config.json' }}</div>
              <el-button
                v-if="p.needs_browser" size="small" text type="primary"
                :loading="hub.loginStates[p.id]?.status === 'running'"
                @click="hub.startLogin(p.id)"
              >{{ hub.loginStates[p.id]?.status === 'running' ? '等待扫码…' : (acctState(p.id) ? '重新登录' : '去登录') }}</el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- Run 详情：平台结果 + 分诊决策审计 + 实时 checkpoint -->
    <el-dialog v-model="runDialog" :title="`Run ${runDetail?.id || ''}`" width="640px">
      <template v-if="runDetail">
        <div class="rd-meta">
          <el-tag size="small" :type="runTagType(runDetail.status)" effect="dark">
            {{ runTagText(runDetail.status) }}
          </el-tag>
          <span class="dim">{{ runDetail.title }} · {{ (runDetail.platforms || []).join('、') }}</span>
          <span v-if="runDetail.checkpoint?.node" class="dim">
            当前节点 {{ runDetail.checkpoint.node }}
            <template v-if="runDetail.checkpoint.queue_left">（剩 {{ runDetail.checkpoint.queue_left }} 平台）</template>
          </span>
        </div>

        <div v-if="runDetail.result?.human_task" class="rd-sec rd-human">
          <b>⏸ 人工任务</b>
          <div>{{ runDetail.result.human_task.message }}</div>
          <div v-if="runDetail.result.human_task.edit_url" class="dim">
            <a :href="runDetail.result.human_task.edit_url" target="_blank" class="p-link">
              {{ runDetail.result.human_task.edit_url }}
            </a>
          </div>
        </div>

        <div v-if="runDetail.result?.results?.length" class="rd-sec">
          <b>平台结果</b>
          <div v-for="(r, i) in runDetail.result.results" :key="i" class="rd-line">
            <el-tag size="small" :type="r.ok ? 'success' : 'danger'" effect="plain">{{ r.platform }}</el-tag>
            <span>尝试 {{ r.attempts || 1 }} 次 · {{ r.status || (r.ok ? 'ok' : 'failed') }}</span>
            <span v-if="r.verify" class="dim">验证 {{ r.verify }}</span>
            <span v-if="r.note" class="dim">（{{ r.note }}）</span>
            <span v-if="r.error" class="run-err">{{ r.error }}</span>
          </div>
        </div>

        <div v-if="runDetail.result?.decisions?.length" class="rd-sec">
          <b>分诊决策（审计）</b>
          <div v-for="(d, i) in runDetail.result.decisions" :key="i" class="rd-line">
            <el-tag size="small" effect="plain"
                    :type="d.action === 'retry' ? 'info' : d.action === 'human' ? 'warning' : 'danger'">
              {{ d.action }}
            </el-tag>
            <span>{{ d.platform }} · 第 {{ d.attempts }} 次 · {{ d.by }}</span>
            <span class="dim">{{ d.reason }}</span>
          </div>
        </div>

        <div v-if="runDetail.error" class="rd-sec"><b>错误</b><div class="run-err">{{ runDetail.error }}</div></div>
      </template>
      <template #footer>
        <el-button @click="runDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useHubStore } from '@/stores/hub'
import { api } from '@/api'
import EmptyState from './EmptyState.vue'

const hub = useHubStore()
const tab = ref('human')
const reloading = ref(false)
const resuming = ref('')          // 正在恢复的 run id
const runDialog = ref(false)
const runDetail = ref(null)       // 当前详情 run

onMounted(reloadAll)

async function reloadAll() {
  reloading.value = true
  try {
    await Promise.all([hub.loadPendingHuman(), hub.loadRuns(), hub.loadAllPubs(),
                       hub.loadStatus(), hub.loadPlatforms()])
  } finally { reloading.value = false }
}

function acctState(platform) {
  const a = hub.accounts.find(x => x.platform === platform)
  return a && a.status === 'logined'
}

const goHandle = (it) => it.edit_url && window.open(it.edit_url, '_blank', 'noopener')
const goUrl = (u) => u && window.open(u, '_blank', 'noopener')

async function doResume(run, approved) {
  if (!approved) {
    try {
      await ElMessageBox.confirm(
        `放弃「${run.title || run.id}」的这次运行？该平台会记为失败。`,
        '确认放弃', { type: 'warning', confirmButtonText: '放弃', cancelButtonText: '再想想' })
    } catch { return }
  }
  resuming.value = run.id
  try { await hub.resumeRun(run.id, approved) }
  finally { resuming.value = '' }
}

async function showRun(row) {
  try {
    runDetail.value = await api.runDetail(row.id)
  } catch { runDetail.value = null }
  if (!runDetail.value) return
  runDialog.value = true
}

const tagType = (s) =>
  s === 'ok' ? 'success' : s === 'failed' ? 'danger' : s === 'pending_human' ? 'warning' : 'info'
const tagText = (s) =>
  s === 'ok' ? '已发布' : s === 'failed' ? '失败' : s === 'pending_human' ? '待人工' : '待更新'

const runTagType = (s) =>
  s === 'done' ? 'success' : s === 'failed' ? 'danger'
  : s === 'waiting_human' ? 'warning' : 'info'
const runTagText = (s) =>
  s === 'done' ? '完成' : s === 'failed' ? '失败'
  : s === 'waiting_human' ? '等人工' : '运行中'

const fmtTime = (ts) => {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<style scoped lang="scss">
.manage { height: 100%; }
.tab-badge { margin-left: 4px; }

.human-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.human-card {
  border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px;
  background: var(--line-soft);
  .hc-head { display: flex; align-items: center; gap: 10px; }
  .hc-title { font-size: var(--fs-md, 14px); color: var(--tx-1); overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
  .hc-sub { font-size: var(--fs-xs); color: var(--tx-3); margin: 8px 0 10px; }
  .hc-ops { display: flex; gap: 8px; }
}
.run-card { border-color: var(--warn, #e6a23c); }
.hc-err { color: var(--bad, #f56c6c); margin-top: 4px; word-break: break-all; }
.run-err { color: var(--bad, #f56c6c); font-size: var(--fs-xs); }

.rd-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.rd-sec { border-top: 1px solid var(--line); padding: 10px 0; font-size: var(--fs-xs);
  color: var(--tx-2); b { color: var(--tx-1); display: block; margin-bottom: 6px; } }
.rd-human { border-left: 3px solid var(--warn, #e6a23c); padding-left: 10px; }
.rd-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 4px 0; }

.p-title { color: var(--tx-1); }
.p-link { color: var(--accent-hi); text-decoration: none; &:hover { text-decoration: underline; } }
.dim { color: var(--tx-4); }

.acct-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.acct-card {
  border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px;
  .ac-top { display: flex; align-items: center; justify-content: space-between; }
  .ac-name { color: var(--tx-1); font-size: var(--fs-md, 14px); }
  .ac-sub { font-size: var(--fs-xs); color: var(--tx-3); margin: 8px 0; }
}
</style>
