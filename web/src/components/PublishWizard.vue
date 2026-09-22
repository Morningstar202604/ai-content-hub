<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="v => $emit('update:modelValue', v)"
    title="发布这篇文章"
    width="560px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <el-steps :active="step" align-center finish-status="success" class="wiz-steps">
      <el-step title="选平台" />
      <el-step title="发布" />
      <el-step title="结果" />
    </el-steps>

    <!-- 第 1 步：选平台 -->
    <div v-if="step === 0" class="wiz-body">
      <div class="plat-grid">
        <div
          v-for="p in platforms" :key="p.id"
          class="plat-card"
          :class="{ on: selected.includes(p.id), running: hub.loginStates[p.id]?.status === 'running' }"
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
            :loading="hub.loginStates[p.id]?.status === 'running'"
            @click.stop="hub.startLogin(p.id)"
          >{{ hub.loginStates[p.id]?.status === 'running' ? '等待扫码…' : '登录' }}</el-button>
        </div>
      </div>
      <div style="display:flex;gap:6px;margin-top:10px">
        <el-button size="small" text @click="selected = platforms.map(p => p.id)">全选</el-button>
        <el-button size="small" text @click="selected = []">清空</el-button>
      </div>
      <el-checkbox v-model="draftOnly" style="margin-top:12px">只发草稿（先不着急公开）</el-checkbox>
    </div>

    <!-- 第 2 步：发布中 -->
    <div v-if="step === 1" class="wiz-body wiz-center">
      <el-icon class="spin" :size="34"><Loading /></el-icon>
      <div class="run-title">正在发布，浏览器在后台操作…</div>
      <div class="run-sub">开浏览器 → 导入正文 → 填表单 → 提交，全程约 1 分钟</div>
    </div>

    <!-- 第 3 步：结果 -->
    <div v-if="step === 2" class="wiz-body">
      <div v-for="r in results" :key="r.platform" class="res-row" :class="r.ok ? 'ok' : 'bad'">
        <div class="res-top">
          <el-icon v-if="r.ok"><CircleCheckFilled /></el-icon>
          <el-icon v-else><CircleCloseFilled /></el-icon>
          <b>{{ r.platform }}</b>
          <span v-if="r.warning" class="res-warn">需人工收尾</span>
        </div>
        <div v-if="r.ok && r.post_url" class="res-link">
          <a :href="r.post_url" target="_blank" rel="noopener">{{ r.post_url }}</a>
        </div>
        <div v-else-if="r.ok && r.warning" class="res-note">{{ r.warning }}</div>
        <div v-else-if="!r.ok" class="res-note bad">{{ r.error }}</div>
      </div>
      <div class="wiz-ops">
        <el-button @click="reset">再发一次</el-button>
        <el-button type="primary" @click="goManage">去管理页看全部</el-button>
      </div>
    </div>

    <template #footer>
      <span v-if="step === 0" class="wiz-hint">灰色的平台还没登录，点卡片上的「登录」扫码一次即可</span>
      <template v-if="step === 0">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :disabled="!selected.length" @click="run">开始发布</el-button>
      </template>
      <el-button v-if="step === 2" @click="reset">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElNotification } from 'element-plus'
import { Loading, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { useHubStore } from '@/stores/hub'

const emit = defineEmits(['update:modelValue', 'done'])
const props = defineProps({ modelValue: Boolean })
const hub = useHubStore()

const PLAT_MARKS = {
  zhihu: '知', bilibili: 'B', cnblogs: '博', csdn: 'C', jianshu: '简',
  juejin: '掘', oschina: '开', segmentfault: '思', toutiao: '头'
}
const mark = p => PLAT_MARKS[p.id] || p.name?.[0] || '?'

const step = ref(0)
const selected = ref([])
const draftOnly = ref(false)
const results = ref([])

function toggle(id) {
  const i = selected.value.indexOf(id)
  i >= 0 ? selected.value.splice(i, 1) : selected.value.push(id)
}

async function run() {
  step.value = 1
  try {
    results.value = await hub.publish(selected.value.slice(), draftOnly.value) || []
  } catch {
    results.value = []
  }
  // 有需要人工的：弹常驻通知（用户要求"弹出来提醒我"）
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
  step.value = 2
  emit('done')
}

function reset() {
  step.value = 0
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
.wiz-steps { margin-bottom: 18px; }
.wiz-body { min-height: 200px; }
.wiz-center {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; padding: 30px 0;
  .spin { color: var(--accent-hi); animation: spin 1.1s linear infinite; }
  .run-title { font-size: var(--fs-md, 14px); color: var(--tx-1); }
  .run-sub { font-size: var(--fs-xs); color: var(--tx-3); }
}
@keyframes spin { to { transform: rotate(360deg); } }

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
.wiz-hint { font-size: var(--fs-xs); color: var(--tx-3); margin-right: 10px; }

.res-row {
  border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin-bottom: 10px;
  &.ok .res-top { color: var(--ok); }
  &.bad .res-top { color: var(--bad); }
  .res-top { display: flex; align-items: center; gap: 8px; color: var(--tx-1); }
  .res-warn {
    font-size: var(--fs-xs); color: var(--warn);
    border: 1px solid var(--warn); border-radius: 4px; padding: 0 5px;
  }
  .res-link a { color: var(--accent-hi); font-size: var(--fs-xs); text-decoration: none;
    word-break: break-all; &:hover { text-decoration: underline; } }
  .res-note { font-size: var(--fs-xs); color: var(--tx-3); margin-top: 4px; line-height: 1.5;
    &.bad { color: var(--bad); } }
}
.wiz-ops { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
</style>
