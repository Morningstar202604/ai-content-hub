<template>
  <header class="hdr">
    <el-button v-if="!listDocked" text :icon="Menu" @click="$emit('open-list')" />

    <span class="logo">AI 内容中台</span>
    <el-tag v-if="!aiReady" size="small" type="info" effect="dark">AI 未配置</el-tag>
    <el-tag v-else size="small" type="success" effect="dark">AI 就绪</el-tag>

    <span class="spacer" />

    <el-tooltip content="文章总数 / 已发布 / 待同步" placement="bottom">
      <div style="display:flex;gap:6px">
        <el-tag size="small" effect="plain">文章 {{ stats.articles || 0 }}</el-tag>
        <el-tag size="small" type="success" effect="plain">已发 {{ stats.published || 0 }}</el-tag>
        <el-tag size="small" type="warning" effect="plain">待同步 {{ stats.pending_sync || 0 }}</el-tag>
      </div>
    </el-tooltip>

    <el-button :icon="Refresh" :loading="loading" @click="$emit('reload')">刷新</el-button>
    <el-button :icon="Upload" :disabled="!stats.pending_sync" @click="$emit('sync')">同步待更新</el-button>
    <el-button :icon="MagicStick" type="primary" @click="$emit('ai-write')">AI 写稿</el-button>
    <el-button :icon="Plus" type="success" @click="$emit('new')">新建</el-button>
  </header>
</template>

<script setup>
import { Menu, Refresh, Upload, MagicStick, Plus } from '@element-plus/icons-vue'

defineProps({
  stats: { type: Object, default: () => ({}) },
  aiReady: Boolean,
  loading: Boolean,
  listDocked: Boolean
})
defineEmits(['open-list', 'reload', 'sync', 'ai-write', 'new'])
</script>
