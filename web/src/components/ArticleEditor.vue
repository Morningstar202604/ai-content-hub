<template>
  <div class="pane" style="height:100%">
    <div class="pane-head editor-head">
      <span class="title">{{ article.id ? '#' + article.id : '新文章' }}</span>
      <el-tag v-if="dirty" size="small" type="warning" effect="dark">未保存</el-tag>
      <span class="spacer" />
      <el-radio-group v-model="view" size="small" class="view-switch">
        <el-radio-button value="edit">编辑</el-radio-button>
        <el-radio-button value="split">分屏</el-radio-button>
        <el-radio-button value="preview">预览</el-radio-button>
      </el-radio-group>
      <el-button size="small" :icon="Aim" @click="$emit('ai-rewrite')">
        <span class="btxt">AI 改写</span>
      </el-button>
      <el-button size="small" :icon="Brush" @click="$emit('ai-polish')">
        <span class="btxt">AI 润色</span>
      </el-button>
      <el-button size="small" type="primary" :icon="Check" :loading="saving" @click="$emit('save')">
        <span class="btxt">保存</span>
      </el-button>
    </div>

    <div class="pane-body" style="padding:12px;display:flex;flex-direction:column;gap:10px">
      <el-input
        v-model="article.title"
        size="large"
        placeholder="文章标题"
        style="font-size:17px;font-weight:600"
        @input="touch"
      />

      <el-input
        v-model="article.summary"
        type="textarea"
        :rows="2"
        placeholder="摘要（可选，部分平台用它当描述）"
        @input="touch"
      />

      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <el-input v-model="article.tags" placeholder="标签，逗号分隔" style="max-width:320px" :prefix-icon="PriceTag" @input="touch" />
        <el-select v-model="article.status" style="width:120px" @change="touch">
          <el-option label="草稿" value="draft" />
          <el-option label="已发布" value="published" />
          <el-option label="待审" value="review" />
          <el-option label="归档" value="archived" />
        </el-select>
        <span class="spacer" />
        <span style="font-size:12px;color:var(--el-text-color-secondary)">
          {{ chars }} 字 · 约 {{ Math.ceil(chars / 350) }} 分钟读完
        </span>
      </div>

      <div class="split-view" :class="{ single: view !== 'split' }" style="flex:1;min-height:360px">
        <el-input
          v-if="view !== 'preview'"
          v-model="article.content_md"
          class="md-area"
          type="textarea"
          resize="none"
          placeholder="Markdown 正文…"
          @input="touch"
        />
        <div v-if="view !== 'edit'" class="md-preview" v-html="rendered" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import { Check, PriceTag, Aim, Brush } from '@element-plus/icons-vue'

const props = defineProps({
  article: { type: Object, default: null },
  isNew: Boolean,
  dirty: Boolean,
  saving: Boolean
})
const emit = defineEmits(['save', 'touch', 'ai-rewrite', 'ai-polish'])

const view = ref('split')
const md = new MarkdownIt({ html: true, linkify: true, breaks: false })
const rendered = computed(() =>
  md.render(props.article?.content_md || '')
)
const chars = computed(() => (props.article?.content_md || '').length)
const touch = () => emit('touch')

// 手机默认只看编辑，分屏两栏根本没法用
watch(() => window.innerWidth, w => {
  if (w < 768 && view.value === 'split') view.value = 'edit'
})
</script>
