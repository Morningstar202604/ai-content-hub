<template>
  <header class="hdr">
    <el-button v-if="!listDocked" text :icon="Menu" @click="$emit('open-list')" />

    <BrandLogo :px="26" />

    <span class="hdr-sep" />

    <!-- 中部：状态信息，克制呈现 -->
    <span class="hdr-stats pill" title="文章总数 / 已发布 / 待同步">
      <span class="dot brand" />
      文章 <b>{{ stats.articles || 0 }}</b>
      <span class="sep" />
      <span class="dot ok" />
      已发 <b>{{ stats.published || 0 }}</b>
      <span class="sep" />
      <span class="dot warn" />
      待同步 <b>{{ stats.pending_sync || 0 }}</b>
    </span>

    <span class="spacer" />

    <!-- 右侧：主操作突出，次操作降噪收敛 -->
    <span class="ai-state" :class="{ on: aiReady }" :title="aiReady ? 'AI 服务已连接' : '未配置 AI，去 config.json 填 AI_API_KEY'">
      <span class="dot" :class="aiReady ? 'ok' : 'off'" />
      <span class="txt">{{ aiReady ? 'AI 就绪' : 'AI 未配置' }}</span>
    </span>

    <el-button :icon="Refresh" :loading="loading" text title="刷新" @click="$emit('reload')" />

    <el-dropdown trigger="click" @command="onMore">
      <el-button :icon="MoreFilled" text title="更多" />
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="sync" :disabled="!stats.pending_sync" :icon="Upload">
            同步待更新{{ stats.pending_sync ? `（${stats.pending_sync}）` : '' }}
          </el-dropdown-item>
          <el-dropdown-item command="ai" :icon="MagicStick">AI 写稿</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <span class="hdr-sep" />

    <el-button type="primary" :icon="Plus" @click="$emit('new')">新建</el-button>
  </header>
</template>

<script setup>
import { Menu, Refresh, Upload, MagicStick, Plus, MoreFilled } from '@element-plus/icons-vue'
import BrandLogo from './BrandLogo.vue'

defineProps({
  stats: { type: Object, default: () => ({}) },
  aiReady: Boolean,
  loading: Boolean,
  listDocked: Boolean
})
const emit = defineEmits(['open-list', 'reload', 'sync', 'ai-write', 'new'])

function onMore(cmd) {
  if (cmd === 'sync') emit('sync')
  else if (cmd === 'ai') emit('ai-write')
}
</script>

<style scoped>
.pill .sep {
  width: 1px;
  height: 11px;
  background: var(--line);
  margin: 0 3px;
}

.ai-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-sm);
  color: var(--tx-3);
  padding: 0 4px;
  white-space: nowrap;

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    &.ok { background: var(--ok); animation: pulseDot 2.2s infinite; }
    &.off { background: var(--tx-4); }
  }
  &.on .txt { color: var(--tx-2); }
}
</style>
