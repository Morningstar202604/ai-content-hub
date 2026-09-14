import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

export const useHubStore = defineStore('hub', {
  state: () => ({
    articles: [],
    currentId: null,
    current: null,
    publications: [],
    platforms: [],
    accounts: [],
    stats: {},
    aiReady: false,
    keyword: '',
    filterStatus: '',
    dirty: false,      // 编辑器有未保存改动
    saving: false,
    publishing: false,
    loadingList: false
  }),

  getters: {
    filtered() {
      const kw = this.keyword.trim().toLowerCase()
      return this.articles.filter(a => {
        if (this.filterStatus && a.status !== this.filterStatus) return false
        if (!kw) return true
        return (a.title || '').toLowerCase().includes(kw) ||
               (a.summary || '').toLowerCase().includes(kw)
      })
    },
    currentPubs: (s) => s.publications,
    // 已发布过（有 post_id）的平台，原地更新才有意义
    updatable: (s) => s.publications.filter(p => p.post_id).map(p => p.platform)
  },

  actions: {
    async boot() {
      await Promise.all([this.loadStatus(), this.loadPlatforms(), this.loadList()])
      try { this.aiReady = (await api.aiStatus()).ready } catch { this.aiReady = false }
    },

    async loadStatus() {
      this.stats = await api.status()
      this.accounts = this.stats.accounts || []
    },

    async loadPlatforms() {
      this.platforms = await api.platforms()
    },

    async loadList() {
      this.loadingList = true
      try { this.articles = await api.listArticles() || [] }
      finally { this.loadingList = false }
    },

    async open(id) {
      if (this.dirty && !confirm('有未保存的改动，确定要切换吗？')) return
      this.currentId = id
      this.current = await api.getArticle(id)
      await this.loadPubs()
      this.dirty = false
    },

    async loadPubs() {
      this.publications = this.currentId
        ? (await api.publications(this.currentId) || [])
        : []
    },

    newArticle() {
      this.currentId = null
      this.current = {
        title: '未命名文章',
        content_md: '',
        summary: '',
        tags: '',
        status: 'draft',
        source: 'human'
      }
      this.publications = []
      this.dirty = true
    },

    async save() {
      if (!this.current) return
      this.saving = true
      try {
        if (this.currentId) {
          await api.updateArticle(this.currentId, {
            title: this.current.title,
            content_md: this.current.content_md,
            summary: this.current.summary,
            tags: this.current.tags,
            status: this.current.status
          })
        } else {
          const r = await api.createArticle({
            ...this.current,
            source: 'human'
          })
          this.currentId = r.id
          // 回填 id，否则编辑器标题栏会显示 #undefined
          this.current = { ...this.current, id: r.id }
        }
        this.dirty = false
        ElMessage.success('已保存')
        await Promise.all([this.loadList(), this.loadStatus(), this.loadPubs()])
      } finally { this.saving = false }
    },

    async publish(platforms, draftOnly) {
      if (!this.currentId) { ElMessage.warning('先保存再发布'); return }
      this.publishing = true
      try {
        const r = await api.publish(this.currentId, platforms, draftOnly)
        const bad = (r || []).filter(x => !x.ok)
        if (bad.length === 0) ElMessage.success(`发布成功 ${(r || []).length} 个平台`)
        else ElMessage.warning(`${bad.length} 个平台失败：${bad.map(b => b.platform).join('、')}`)
        await Promise.all([this.loadPubs(), this.loadStatus(), this.loadList()])
        return r
      } finally { this.publishing = false }
    },

    async updateRemote(platforms) {
      if (!this.currentId) return
      this.publishing = true
      try {
        const r = await api.update(this.currentId, platforms)
        const bad = (r || []).filter(x => !x.ok)
        if (bad.length === 0) ElMessage.success('原地更新完成')
        else ElMessage.warning(`${bad.length} 个平台更新失败`)
        await Promise.all([this.loadPubs(), this.loadStatus()])
        return r
      } finally { this.publishing = false }
    },

    async syncPending() {
      await api.syncPending()
      ElMessage.success('同步完成')
      await Promise.all([this.loadStatus(), this.loadPubs()])
    },

    async refreshPlatform(pf) {
      const r = await api.refresh(pf)
      ElMessage.success(`抓回 ${r.count} 篇`)
      await this.loadList()
      return r
    }
  }
})
