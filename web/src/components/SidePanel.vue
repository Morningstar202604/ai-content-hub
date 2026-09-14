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
        <span class="lbl">目标平台（点选，支持多选）</span>
        <div class="plat-grid">
          <div
            v-for="p in platforms" :key="p.id"
            class="plat-card"
            :class="{ on: selected.includes(p.id) }"
            @click="toggle(p.id)"
          >
            <div class="n">{{ p.name }}</div>
            <div class="s">{{ p.needs_browser ? '浏览器' : '免登 API' }}</div>
          </div>
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
        <div v-if="!updatable.length" style="font-size:11px;color:var(--el-text-color-secondary);margin-top:6px">
          还没发布过，先发布一次才能原地更新
        </div>
      </div>

      <!-- 发布实例 -->
      <div class="side-block">
        <span class="lbl">发布实例</span>
        <el-table :data="pubs" size="small" max-height="260">
          <el-table-column prop="platform" label="平台" width="76" />
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
              <a v-if="row.post_url" :href="row.post_url" target="_blank" rel="noopener">
                {{ row.post_id || '打开' }}
              </a>
              <span v-else style="color:var(--el-text-color-secondary)">{{ row.post_id || '-' }}</span>
              <div v-if="row.last_error" style="color:#f85149;font-size:10px" :title="row.last_error">
                {{ row.last_error.slice(0, 30) }}…
              </div>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!pubs.length" description="还没有发布记录" :image-size="50" />
      </div>

      <!-- 账号状态 -->
      <div class="side-block">
        <span class="lbl">账号登录态</span>
        <div v-for="a in accounts" :key="a.platform + a.name"
             style="display:flex;align-items:center;gap:6px;margin-bottom:6px;font-size:12px">
          <el-tag size="small" :type="a.status === 'logined' ? 'success' : 'danger'" effect="dark">
            {{ a.status === 'logined' ? '在线' : '离线' }}
          </el-tag>
          <span>{{ a.platform }} / {{ a.name }}</span>
        </div>
        <el-empty v-if="!accounts.length" description="还没有登录任何平台" :image-size="50" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Promotion, RefreshLeft, RefreshRight } from '@element-plus/icons-vue'

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
</script>
