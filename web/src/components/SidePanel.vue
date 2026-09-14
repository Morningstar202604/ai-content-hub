<template>
  <div class="pane" style="height:100%">
    <div class="pane-head">
      <span class="title">发布与同步</span>
      <span class="spacer" />
      <el-button size="small" text :icon="RefreshRight" :loading="refreshing" @click="$emit('refresh')">抓平台文章</el-button>
    </div>

    <div class="pane-body">
      <!-- 平台选择 -->
      <div class="side-block">
        <span class="lbl">目标平台<i class="tip">点选，支持多选</i></span>
        <div class="plat-grid">
          <div
            v-for="p in platforms" :key="p.id"
            class="plat-card"
            :class="{ on: selected.includes(p.id), running: loginState[p.id]?.status === 'running' }"
            @click="toggle(p.id)"
          >
            <div class="plat-top">
              <span class="plat-badge" :style="{ background: PLAT_COLORS[p.id] || '#64748B' }">{{ badgeMark(p) }}</span>
              <div class="nn">
                <div class="n">{{ p.name }}</div>
                <div class="s">{{ p.needs_browser ? '浏览器' : '免登 API' }}</div>
              </div>
            </div>
            <el-button
              class="login-btn" size="small" text type="primary"
              :loading="loginState[p.id]?.status === 'running'"
              @click.stop="startLogin(p.id)"
            >{{ loginState[p.id]?.status === 'running' ? '等待扫码…' : '登录' }}</el-button>
          </div>
        </div>
        <div v-if="loginHint" class="login-hint">
          <span class="hint-ico">⌖</span>{{ loginHint }}
        </div>
        <div style="margin-top:8px;display:flex;gap:6px">
          <el-button size="small" text @click="selected = platforms.map(p => p.id)">全选</el-button>
          <el-button size="small" text @click="selected = []">清空</el-button>
          <el-button size="small" text @click="selected = platforms.filter(p => !p.needs_browser).map(p => p.id)">
            只选免登
          </el-button>
        </div>
      </div>

      <!-- 发布动作 -->
      <div class="side-block">
        <el-checkbox v-model="draftOnly">只发草稿（先不着急公开）</el-checkbox>
        <div style="display:flex;gap:8px;margin-top:10px">
          <el-button type="primary" :icon="Promotion" :loading="busy" :disabled="!selected.length" style="flex:1"
                     @click="doPublish">
            发布
          </el-button>
          <el-button :icon="RefreshLeft" :loading="busy" :disabled="!updatable.length" style="flex:1"
                     @click="doUpdate">
            原地更新
          </el-button>
        </div>
        <div v-if="!updatable.length" class="micro-hint">
          还没发布过，先发布一次才能原地更新
        </div>
      </div>

      <!-- 发布实例 -->
      <div class="side-block">
        <span class="lbl">发布实例</span>
        <el-table v-if="pubs.length" :data="pubs" size="small" max-height="260">
          <el-table-column label="平台" width="76">
            <template #default="{ row }">
              <span class="pub-plat">
                <i class="mini-dot" :style="{ background: PLAT_COLORS[row.platform] || '#64748B' }" />
                {{ row.platform }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="82">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === 'ok' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'"
                      effect="dark">
                {{ row.status === 'ok' ? '已同步' : row.status === 'failed' ? '失败' : '待更新' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="ID / 链接">
            <template #default="{ row }">
              <a v-if="row.post_url" class="pub-link" :href="row.post_url" target="_blank" rel="noopener">
                {{ row.post_id || '打开' }}
              </a>
              <span v-else class="dim">{{ row.post_id || '-' }}</span>
              <div v-if="row.last_error" class="pub-err" :title="row.last_error">
                {{ row.last_error.slice(0, 30) }}…
              </div>
            </template>
          </el-table-column>
        </el-table>
        <EmptyState v-else title="还没有发布记录" desc="勾选平台后点「发布」，实例会落在这里" :px="96" />
      </div>

      <!-- 账号状态 -->
      <div class="side-block">
        <span class="lbl">账号登录态</span>
        <div v-for="(a, i) in accounts" :key="a.platform + a.name" class="acct-row" :style="{ '--i': i }">
          <el-tag size="small" :type="a.status === 'logined' ? 'success' : 'info'" effect="dark">
            {{ a.status === 'logined' ? '在线' : '离线' }}
          </el-tag>
          <span class="mini-dot" :style="{ background: PLAT_COLORS[a.platform] || '#64748B' }" />
          <span class="acct-name">{{ a.platform }} / {{ a.name }}</span>
        </div>
        <EmptyState v-if="!accounts.length" title="还没有登录任何平台" desc="点上方平台卡片的「登录」，扫码一次就长期在线" :px="96" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, RefreshLeft, RefreshRight } from '@element-plus/icons-vue'
import { api } from '@/api'
import { useHubStore } from '@/stores/hub'
import EmptyState from './EmptyState.vue'

const hub = useHubStore()

// 平台品牌色 + 徽标字（改版只动这里）
const PLAT_COLORS = {
  zhihu: '#0084FF',
  bilibili: '#FB7299',
  cnblogs: '#2FA8A0',
  csdn: '#FC5531',
  jianshu: '#EA6F5A',
  juejin: '#1E80FF',
  oschina: '#2CC067',
  segmentfault: '#14B8A6',
  toutiao: '#F04142'
}
const PLAT_MARKS = {
  zhihu: '知', bilibili: 'B', cnblogs: '博', csdn: 'C', jianshu: '简',
  juejin: '掘', oschina: '开', segmentfault: '思', toutiao: '头'
}
const badgeMark = p => PLAT_MARKS[p.id] || p.name?.[0] || '?'

const props = defineProps({
  platforms: { type: Array, default: () => [] },
  pubs: { type: Array, default: () => [] },
  accounts: { type: Array, default: () => [] },
  busy: Boolean,
  refreshing: Boolean
})
const emit = defineEmits(['publish', 'update', 'refresh'])

const selected = ref([])
const draftOnly = ref(false)
const updatable = ref([])
const loginState = ref({})   // platform -> {status, message}

// 登录成功后顺便提示一下（账号态列表由 hub.loadStatus 刷新）
const loginHint = ref('')

// 已发布的平台默认勾上，符合"改完直接更新"的直觉
watch(() => props.pubs, list => {
  updatable.value = list.filter(p => p.post_id).map(p => p.platform)
}, { immediate: true, deep: true })

function toggle(id) {
  const i = selected.value.indexOf(id)
  i >= 0 ? selected.value.splice(i, 1) : selected.value.push(id)
}
const doPublish = () => emit('publish', [...selected.value], draftOnly.value)
const doUpdate = () => emit('update', [...updatable.value])

// ---- 登录：点按钮开浏览器去平台登录页，人扫码，程序轮询登录态 ----
async function startLogin(platform) {
  if (loginState.value[platform]?.status === 'running') return
  try {
    const t = await api.startLogin(platform)
    loginState.value[platform] = { status: 'running', message: '等待扫码…' }
    loginHint.value = `已打开${platform}登录页，请在新弹出的浏览器窗口扫码；完成后这里自动变绿。`
    const timer = setInterval(async () => {
      try {
        const s = await api.loginStatus(platform, t.task_id)
        loginState.value[platform] = s
        if (s.status === 'success') {
          clearInterval(timer)
          loginHint.value = ''
          ElMessage.success(`${platform} 登录成功，登录态已保存，以后自动复用`)
          await hub.loadStatus()          // 刷新账号在线状态
        } else if (s.status === 'failed') {
          clearInterval(timer)
          loginHint.value = `${platform} 登录失败：${s.message || '未知原因'}`
        }
      } catch { /* 轮询偶发失败忽略，下轮再试 */ }
    }, 2000)
  } catch { /* api.js 拦截器已弹错误提示 */ }
}
</script>

<style scoped lang="scss">
.tip {
  font-style: normal;
  font-weight: 400;
  letter-spacing: 0;
  margin-left: auto;
  color: var(--el-text-color-placeholder);
  font-size: 10.5px;
}
.hint-ico { margin-right: 5px; }
.micro-hint {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-top: 7px;
}

.pub-plat {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-variant-numeric: tabular-nums;
}
.mini-dot {
  width: 7px;
  height: 7px;
  border-radius: 2.5px;
  flex-shrink: 0;
  display: inline-block;
}
.pub-link {
  color: #9F8CFF;
  text-decoration: none;
  font-variant-numeric: tabular-nums;
  &:hover { text-decoration: underline; }
}
.dim { color: var(--el-text-color-placeholder); }
.pub-err {
  color: var(--bad);
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// 账号行
.acct-name { flex: 1; font-variant-numeric: tabular-nums; }
</style>
