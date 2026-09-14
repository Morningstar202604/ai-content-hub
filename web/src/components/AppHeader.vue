<template>
  <header class="hdr">
    <el-button v-if="!listDocked" text :icon="Menu" @click="$emit('open-list')" />

    <BrandLogo :px="30" />

    <span class="pill" :title="aiReady ? 'AI 服务已连接' : '未配置 AI，去 config.json 填 AI_API_KEY'">
      <span class="dot" :class="aiReady ? 'ok' : 'off'" />
      {{ aiReady ? 'AI 就绪' : 'AI 未配置' }}
    </span>

    <span class="spacer" />

    <span class="pill" title="文章总数 / 已发布 / 待同步">
      <span class="dot brand" />
      文章 <b>{{ stats.articles || 0 }}</b>
      <span class="sep" />
      <span class="dot ok" />
      已发 <b>{{ stats.published || 0 }}</b>
      <span class="sep" />
      <span class="dot warn" />
      待同步 <b>{{ stats.pending_sync || 0 }}</b>
    </span>

    <el-button :icon="Refresh" :loading="loading" @click="$emit('reload')">刷新</el-button>
    <el-button :icon="Upload" :disabled="!stats.pending_sync" @click="$emit('sync')">同步待更新</el-button>
    <el-button :icon="MagicStick" type="primary" plain @click="$emit('ai-write')">AI 写稿</el-button>
    <el-button :icon="Plus" type="primary" @click="$emit('new')">新建</el-button>
  </header>
</template>

<script setup>
import { Menu, Refresh, Upload, MagicStick, Plus } from '@element-plus/icons-vue'
import BrandLogo from './BrandLogo.vue'

defineProps({
  stats: { type: Object, default: () => ({}) },
  aiReady: Boolean,
  loading: Boolean,
  listDocked: Boolean
})
defineEmits(['open-list', 'reload', 'sync', 'ai-write', 'new'])
</script>

<style scoped>
.pill .sep {
  width: 1px;
  height: 11px;
  background: var(--ach-line);
  margin: 0 3px;
}
</style>
