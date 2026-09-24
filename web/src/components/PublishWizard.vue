<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="v => $emit('update:modelValue', v)"
    title="发布这篇文章"
    width="600px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <!-- 发布中：紧凑进度条，不做"假装复杂的步骤页" -->
    <div v-if="running" class="pub-progress">
      <el-progress :percentage="progressPct" :stroke-width="10" :show-text="false" />
      <div class="pub-progress-note">
        <el-icon class="spin"><Loading /></el-icon>
        正在发往 {{ selected.length }} 个平台（开浏览器 → 导入正文 → 提交）…
      </div>
    </div>

    <!-- 选择平台 -->
    <div v-if="!running" class="pub-body">
      <div class="plat-grid">
        <div
          v-for="p in platforms" :key="p.id"
          class="plat-card"
          :class="{ on: selected.includes(p.id) }"
          @click="toggle(p.id)"
        >
          <div class="plat-top">
            <span class="plat-badge">{{ mark(p) }}</span>
            <div class="nn">
              <div class="n">{{ p.name }}</div>
              <div class="s">{{ p.needs_browser ? '浏览器' : '免登 API' }}</div>
            </div>
          </div>
          <el-button
            class="login-btn" size="small" text type="primary"
            :loading="hub.loginTasks[p.id]?.status === 'running'"
            @click.stop="hub.startLogin(p.id)"
          >{{ hub.loginTasks[p.id]?.status === 'running' ? '等待扫码…' : '登录' }}</el-button>
        </div>
      </div>
      <div class="pub-tools">
        <el-button size="small" text @click="selected = platforms.map(p => p.id)">全选</el-button>
        <el-button size="small" text @click="selected = []">清空</el-button>
        <span class="pub-hint">灰色的平台先点「登录」扫码一次，之后自动复用</span>
      </div>
      <el-checkbox v-model="draftOnly">只发草稿（先不公开，回头在平台上手动发布）</el-checkbox>
    </div>

    <!-- 结果 -->
    <div v-if="done" class="pub-results">
      <div v-for="r in results" :key="r.platform" class="res-row" :class="r.ok ? 'ok' : 'bad'">
        <div class="res-top">
          <el-icon v-if="r.ok"><CircleCheckFilled /></el-icon>
          <el-icon v-else><CircleCloseFilled /></el-icon>
          <b>{{ r.platform }}</b>
          <span v-if="r.warning" class="res-warn">需人工收尾</span>
          <span v-else-if="r.skipped" class="res-warn skip">已跳过</span>
        </div>
        <div v-if="r.ok && r.post_url" class="res-link">
          <a :href="r.post_url" target="_blank" rel="noopener">{{ r.post_url }}</a>
        </div>
        <div v-else-if="r.ok && r.warning" class="res-note">{{ r.warning }}</div>
        <div v-else-if="!r.ok" class="res-note bad">{{ r.error }}</div>
      </div>
      <div class="pub-ops">
        <el-button @click="reset">再发一次</el-button>
        <el-button type="primary" @click="goManage">去管理页看全部</el-button>
      </div>
    </div>

    <template #footer>
      <template v-if="!running && !done">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :disabled="!selected.length" @click="run">
          发布到 {{ selected.length }} 个平台
        </el-button>
      </template>
      <el-button v-if="done" @click="reset">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElNotification, ElMessage } from 'element-plus'
import { Loading, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { useHubStore } from '@/stores/hub'

const emit = defineEmits(['update:modelValue', 'done'])
const props = defineProps({
  modelValue: Boolean,
  platforms: { type: Array, default: () => [] },
})
const hub = useHubStore()

const PLAT_MARKS = {
  zhihu: '知', bilibili: 'B', cnblogs: '博', csdn: 'C', jianshu: '简',
  juejin: '掘', oschina: '开', segmentfault: '思', toutiao: '头'
}
const mark = p => PLAT_MARKS[p.id] || p.name?.[0] || '?'

const selected = ref([])
const draftOnly = ref(false)
const running = ref(false)
const done = ref(false)
const results = ref([])
const progressPct = computed(() => results.value.length
  ? Math.min(95, Math.round(results.value.length / selected.value.length * 100))
  : running.value ? 15 : 0)

function toggle(id) {
  const i = selected.value.indexOf(id)
  i >= 0 ? selected.value.splice(i, 1) : selected.value.push(id)
}

async function run() {
  running.value = true
  done.value = false
  results.value = []
  try {
    const t = await hub.publish(selected.value.slice(), draftOnly.value)
    if (!t) return
    const res = t.result || {}
    results.value = Array.isArray(res) ? res : (res.results || [])
    // 需要人工的弹常驻通知
    for (const r of results.value) {
      if (r.ok && r.warning) {
        ElNotification({
          title: `${r.platform} 需要人工收尾`,
          message: (r.warning || '').slice(0, 120),
          type: 'warning', duration: 0
        })
      }
    }
    await hub.loadPendingHuman()
  } catch (e) {
    // 合规门禁/其他拒绝：把原因亮出来，停留在选择界面让用户调整（如勾"只发草稿"）
    results.value = []
    ElMessage.error(e?.response?.data?.detail || e?.message || '发布失败，请查看任务记录')
  }
  running.value = false
  if (results.value.length) {
    done.value = true
    emit('done')
  }
}

function reset() {
  running.value = false
  done.value = false
  results.value = []
  selected.value = []
  emit('update:modelValue', false)
}

function goManage() {
  reset()
  hub.switchView('manage')
}
</script>

<style scoped lang="scss">
.spin { animation: spin 1.1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.pub-progress {
  padding: 14px 0;
  .pub-progress-note {
    display: flex; align-items: center; gap: 8px;
    margin-top: 10px; font-size: 12px; color: var(--tx-3);
    .spin { color: var(--accent-hi); }
  }
}

.plat-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px;
}
.plat-card {
  border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px;
  cursor: pointer; transition: border-color .15s, background .15s;
  &:hover { border-color: var(--line-strong); }
  &.on { border-color: var(--accent-hi); background: rgba(232, 190, 108, .06); }
  .plat-top { display: flex; align-items: center; gap: 9px; }
  .plat-badge {
    width: 30px; height: 30px; border-radius: 8px; background: var(--line-soft);
    display: inline-flex; align-items: center; justify-content: center;
    color: var(--tx-2); font-weight: 600; flex-shrink: 0;
  }
  .nn .n { font-size: var(--fs-sm); color: var(--tx-1); }
  .nn .s { font-size: 10px; color: var(--tx-3); }
  .login-btn { padding: 2px 0; height: auto; margin-top: 4px; }
}
.pub-tools { display: flex; align-items: center; gap: 6px; margin-top: 10px; }
.pub-hint { font-size: 11px; color: var(--tx-3); margin-left: auto; }
.pub-body > .el-checkbox { margin-top: 10px; }

.res-row {
  border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin-bottom: 10px;
  &.ok .res-top { color: var(--ok); }
  &.bad .res-top { color: var(--bad); }
  .res-top { display: flex; align-items: center; gap: 8px; color: var(--tx-1); }
  .res-warn {
    font-size: 11px; color: var(--warn);
    border: 1px solid var(--warn); border-radius: 4px; padding: 0 5px;
    &.skip { color: var(--tx-3); border-color: var(--line-strong); }
  }
  .res-link a { color: var(--accent-hi); font-size: 12px; text-decoration: none;
    word-break: break-all; &:hover { text-decoration: underline; } }
  .res-note { font-size: 12px; color: var(--tx-3); margin-top: 4px; line-height: 1.5;
    &.bad { color: var(--bad); } }
}
.pub-ops { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
</style>
