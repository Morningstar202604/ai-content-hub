<template>
  <div class="pane" style="height:100%">
    <div class="pane-head editor-head">
      <span class="title">{{ article.id ? '#' + article.id : '新文章' }}</span>
      <el-tag v-if="dirty" size="small" type="warning" effect="dark" class="dirty-tag">未保存</el-tag>
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

    <div class="pane-body editor-body">
      <el-input
        v-model="article.title"
        size="large"
        placeholder="文章标题"
        class="title-input"
        @input="touch"
      />

      <el-input
        v-model="article.summary"
        type="textarea"
        :rows="2"
        placeholder="摘要（可选，部分平台用它当描述）"
        @input="touch"
      />

      <div class="meta-row">
        <el-input v-model="article.tags" placeholder="标签，逗号分隔" class="tags-input" :prefix-icon="PriceTag" @input="touch" />
        <el-select v-model="article.status" class="status-sel" @change="touch">
          <el-option label="草稿" value="draft" />
          <el-option label="已发布" value="published" />
          <el-option label="待审" value="review" />
          <el-option label="归档" value="archived" />
        </el-select>
        <span class="spacer" />
        <span class="meta-chip">
          {{ chars }} 字 · 约 {{ Math.ceil(chars / 350) }} 分钟读完
        </span>
      </div>

      <div class="split-view" :class="{ single: view !== 'split' }">
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
import { useBreakpoint } from '@/composables/useBreakpoint'

const props = defineProps({
  article: { type: Object, default: null },
  isNew: Boolean,
  dirty: Boolean,
  saving: Boolean
})
const emit = defineEmits(['save', 'touch', 'ai-rewrite', 'ai-polish'])

const { isMobile } = useBreakpoint()
// 手机默认只看编辑，分屏两栏根本没法用；桌面默认分屏
const view = ref(isMobile.value ? 'edit' : 'split')
// 用响应式断点监听：从桌面拖窄到手机时，若还停在分屏就切回编辑
watch(isMobile, m => { if (m && view.value === 'split') view.value = 'edit' })

const md = new MarkdownIt({ html: true, linkify: true, breaks: false })
const rendered = computed(() =>
  md.render(props.article?.content_md || '')
)
const chars = computed(() => (props.article?.content_md || '').length)
const touch = () => emit('touch')
</script>

<style scoped lang="scss">
.dirty-tag {
  animation: popIn .2s var(--ease-out);
}
.title-input :deep(.el-input__inner) {
  font-size: var(--fs-xl);
  font-weight: 600;
  letter-spacing: -.01em;
}

.editor-body {
  padding: 14px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.meta-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.tags-input { max-width: 300px; }
.status-sel { width: 116px; }
.meta-row .spacer { flex: 1; }

// 分屏容器撑满剩余高度
.split-view { flex: 1; min-height: 0; }
</style>
