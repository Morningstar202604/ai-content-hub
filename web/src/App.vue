<template>
  <div class="app">
    <!-- 全局动作进度条：加载/保存/发布任一进行中就亮 -->
    <div class="top-progress" :class="{ show: hub.loadingList || hub.saving || hub.publishing }" />

    <AppHeader
      :stats="hub.stats"
      :ai-ready="hub.aiReady"
      :loading="hub.loadingList"
      :list-docked="listDocked"
      @open-list="listDrawer = true"
      @reload="hub.boot()"
      @sync="hub.syncPending()"
      @ai-write="aiDialog = true"
      @new="hub.newArticle()"
    />

    <main class="layout" :class="{ 'docked-list': listDocked, 'docked-side': sideDocked }">
      <ArticleList
        v-if="listDocked"
        v-model:keyword="hub.keyword"
        v-model:status="hub.filterStatus"
        :articles="hub.articles"
        :current-id="hub.currentId"
        :loading="hub.loadingList"
        @open="onOpen"
        @new-article="hub.newArticle()"
      />

      <ArticleEditor
        v-if="hub.current"
        :article="hub.current"
        :is-new="!hub.currentId"
        :dirty="hub.dirty"
        :saving="hub.saving"
        @save="hub.save()"
        @touch="hub.dirty = true"
        @ai-rewrite="onRewrite"
        @ai-polish="onPolish"
      />
      <div v-else class="pane pane-center">
        <EmptyState
          :px="168"
          title="开始写一稿"
          desc="选一篇文章继续编辑，或者新建一篇，写完勾选平台一键发全网"
        >
          <el-button type="primary" :icon="Plus" @click="hub.newArticle()">新建文章</el-button>
          <el-button :icon="MagicStick" @click="aiDialog = true">让 AI 写</el-button>
        </EmptyState>
      </div>

      <SidePanel
        v-if="sideDocked"
        :platforms="hub.platforms"
        :pubs="hub.publications"
        :accounts="hub.accounts"
        :busy="hub.publishing"
        :refreshing="refreshing"
        @publish="(p, d) => hub.publish(p, d)"
        @update="hub.updateRemote($event)"
        @refresh="onRefresh"
      />
    </main>

    <!-- 窄屏：列表和侧栏改成抽屉 -->
    <el-drawer v-if="!listDocked" v-model="listDrawer" direction="ltr" size="86%" :with-header="false">
      <ArticleList
        v-model:keyword="hub.keyword"
        v-model:status="hub.filterStatus"
        :articles="hub.articles"
        :current-id="hub.currentId"
        :loading="hub.loadingList"
        @open="id => { onOpen(id); listDrawer = false }"
      />
    </el-drawer>

    <el-drawer v-if="!sideDocked" v-model="sideDrawer" direction="rtl" size="86%" :with-header="false">
      <SidePanel
        :platforms="hub.platforms"
        :pubs="hub.publications"
        :accounts="hub.accounts"
        :busy="hub.publishing"
        :refreshing="refreshing"
        @publish="(p, d) => hub.publish(p, d)"
        @update="hub.updateRemote($event)"
        @refresh="onRefresh"
      />
    </el-drawer>

    <!-- 手机端浮动操作条：没有侧栏，必须给个入口 -->
    <div v-if="!sideDocked" class="fab" @click="sideDrawer = true">
      <el-icon><Promotion /></el-icon>
      <span>发布</span>
    </div>

    <AIWriteDialog
      v-model="aiDialog"
      :platforms="hub.platforms"
      :ready="hub.aiReady"
      @done="hub.open($event)"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Promotion, Plus, MagicStick } from '@element-plus/icons-vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useHubStore } from '@/stores/hub'
import { api } from '@/api'
import AppHeader from '@/components/AppHeader.vue'
import ArticleList from '@/components/ArticleList.vue'
import ArticleEditor from '@/components/ArticleEditor.vue'
import SidePanel from '@/components/SidePanel.vue'
import AIWriteDialog from '@/components/AIWriteDialog.vue'
import EmptyState from '@/components/EmptyState.vue'

const hub = useHubStore()
const { listDocked, sideDocked } = useBreakpoint()

const listDrawer = ref(false)
const sideDrawer = ref(false)
const aiDialog = ref(false)
const refreshing = ref(false)

onMounted(() => hub.boot())

// 从窄屏变宽屏时把抽屉收起来，免得残留遮罩
watch([listDocked, sideDocked], ([l, s]) => {
  if (l) listDrawer.value = false
  if (s) sideDrawer.value = false
})

async function onOpen(id) {
  await hub.open(id)
  listDrawer.value = false
}

async function onRewrite() {
  if (!hub.currentId) return
  try {
    const { value } = await ElMessageBox.prompt(
      '例如：多给两个代码示例 / 语气更口语 / 压缩到 800 字',
      'AI 改写', { inputPlaceholder: '改写要求', inputType: 'textarea' }
    )
    await hub.save()
    await api.aiRewrite(hub.currentId, value)
    await hub.open(hub.currentId)
  } catch { /* 用户取消 */ }
}

async function onPolish() {
  if (!hub.currentId) return
  await hub.save()
  await api.aiPolish(hub.currentId)
  await hub.open(hub.currentId)
}

async function onRefresh() {
  try {
    const { value } = await ElMessageBox.prompt(
      '从哪个平台把已发文章抓回本地？', '抓取平台文章',
      { inputPlaceholder: hub.platforms[0]?.id || 'cnblogs' }
    )
    refreshing.value = true
    await hub.refreshPlatform(value.trim())
  } catch { /* 取消 */ }
  finally { refreshing.value = false }
}
</script>

<style scoped lang="scss">
.pane-center {
  align-items: center;
  justify-content: center;
}

.fab {
  position: fixed;
  right: 18px;
  bottom: 24px;
  z-index: 2000;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 22px;
  border-radius: 26px;
  background: linear-gradient(135deg, #6D5CFF, #C44BFF);
  color: #fff;
  font-size: 14px;
  font-weight: 650;
  box-shadow: 0 8px 26px rgba(124, 92, 255, .5);
  cursor: pointer;
  user-select: none;
  transition: all .2s cubic-bezier(.22, 1, .36, 1);

  &:hover { transform: translateY(-2px); box-shadow: 0 12px 30px rgba(124, 92, 255, .65); }
  &:active { transform: scale(.96); }
}
</style>
