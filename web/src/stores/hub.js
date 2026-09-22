import { defineStore } from 'pinia'
import { ElMessage, ElNotification, ElMessageBox } from 'element-plus'
import { api } from '@/api'

export const useHubStore = defineStore('hub', {
  state: () => ({
    articles: [],
    currentId: null,
    current: null,
    publications: [],
    allPubs: [],        // 全部发布实例（管理视图用，带文章标题）
    platforms: [],
    accounts: [],
    stats: {},
    aiReady: false,
    pendingHuman: [],   // 需要人工处理的发布实例（掘金草稿等人点发布）
    runs: [],           // 工作流运行列表（LangGraph，ADR-001）
    loginStates: {},    // platform -> {status, message}，登录轮询状态（向导/管理页共用）
    keyword: '',
    filterStatus: '',
    dirty: false,      // 编辑器有未保存改动
    saving: false,
    publishing: false,
    loadingList: false,
    view: localStorage.getItem('hub_view') || 'write'   // write=写作 / manage=管理
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
    updatable: (s) => s.publications.filter(p => p.post_id).map(p => p.platform),
    // 挂起等人工的工作流 run（等待卡片墙）
    waitingRuns: (s) => s.runs.filter(r => r.status === 'waiting_human')
  },

  actions: {
    switchView(v) {
      this.view = v
      localStorage.setItem('hub_view', v)
    },

    async boot() {
      await Promise.all([this.loadStatus(), this.loadPlatforms(), this.loadList(),
                         this.loadPendingHuman(), this.loadRuns()])
      try { this.aiReady = (await api.aiStatus()).ready } catch { this.aiReady = false }
      // 需要人工的任务定时巡检：一旦出现新条目就弹通知（用户要求"弹出来提醒我"）
      this._phTimer && clearInterval(this._phTimer)
      this._phLast = this.pendingHuman.length
      this._phTimer = setInterval(() => {
        this.loadPendingHuman(true)
        this.loadRuns(true)
      }, 30000)
    },

    async loadRuns(notify = false) {
      try {
        const list = await api.runs() || []
        const prevWaiting = new Set(this.runs
          .filter(r => r.status === 'waiting_human').map(r => r.id))
        this.runs = list
        if (notify) {
          for (const r of list.filter(
            x => x.status === 'waiting_human' && !prevWaiting.has(x.id))) {
            ElNotification({
              title: '工作流等待人工确认',
              message: `「${r.title || '未命名'}」${r.human_task?.platform || ''}：` +
                       `${r.human_task?.message || '挂起中，到管理页处理'}`,
              type: 'warning', duration: 0
            })
          }
        }
      } catch { /* 轮询失败静默 */ }
    },

    async resumeRun(runId, approved = true, note = '') {
      await api.resumeRun(runId, approved, note)
      ElMessage.success(approved ? '已恢复，工作流继续执行' : '已放弃该 run')
      await Promise.all([this.loadRuns(), this.loadPendingHuman(),
                         this.loadPubs(), this.loadAllPubs(), this.loadStatus()])
    },

    async loadPendingHuman(notify = false) {
      try {
        const list = await api.pendingHuman() || []
        const prevIds = new Set(this.pendingHuman.map(x => x.platform + x.post_id + x.article_id))
        this.pendingHuman = list
        if (notify) {
          const fresh = list.filter(x => !prevIds.has(x.platform + x.post_id + x.article_id))
          for (const it of fresh) {
            ElNotification({
              title: '需要人工处理',
              message: `「${it.title || '未命名'}」已发到 ${it.platform} 草稿，到「管理 → 需要人工」去完成最后一步`,
              type: 'warning', duration: 0
            })
          }
        }
      } catch { /* 轮询失败静默 */ }
    },

    async loadAllPubs() {
      this.allPubs = await api.publications() || []
    },

    // 登录流程下沉到 store：发布向导和管理视图共用同一份轮询状态
    async startLogin(platform) {
      if (this.loginStates[platform]?.status === 'running') return
      const t = await api.startLogin(platform)
      this.loginStates[platform] = { status: 'running', message: '等待扫码…' }
      const timer = setInterval(async () => {
        try {
          const s = await api.loginStatus(platform, t.task_id)
          this.loginStates[platform] = s
          if (s.status === 'success' || s.status === 'failed') {
            clearInterval(timer)
            if (s.status === 'success') {
              ElMessage.success(`${platform} 登录成功，以后自动复用`)
              await this.loadStatus()
            }
          }
        } catch { /* 轮询偶发失败忽略 */ }
      }, 2000)
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
      if (this.dirty) {
        try {
          await ElMessageBox.confirm(
            '当前文章有未保存的改动，切换会丢失这些改动。确定切换吗？',
            '未保存的改动', { type: 'warning', confirmButtonText: '确定切换', cancelButtonText: '留在这' }
          )
        } catch { return }   // 用户取消，留在当前文章
      }
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
        // 首选工作流引擎（ADR-003 绞杀者）：仅"启动失败"回退 legacy；
        // 启动成功后只轮询、任何异常都向上抛——绝不回退，否则引擎还在跑、
        // legacy 又发一遍 = 同一篇文章双发到平台。
        const start = await api.publishWorkflow(
          this.currentId, platforms, draftOnly).catch(() => null)
        const r = start?.run_id
          ? await this._pollWorkflowRows(start.run_id, platforms)
          : await api.publish(this.currentId, platforms, draftOnly)
        const bad = (r || []).filter(x => !x.ok)
        if (bad.length === 0) ElMessage.success(`发布成功 ${(r || []).length} 个平台`)
        else ElMessage.warning(`${bad.length} 个平台失败：${bad.map(b => b.platform).join('、')}`)
        // 有平台需要人工收尾（如掘金草稿）：立即弹通知 + 刷新待人工清单
        const needHuman = (r || []).filter(x => x.warning)
        for (const x of needHuman) {
          ElNotification({
            title: `${x.platform} 需要人工收尾`,
            message: (x.warning || '').slice(0, 120),
            type: 'warning', duration: 0
          })
        }
        if (needHuman.length) await Promise.all([this.loadPendingHuman(), this.loadRuns()])
        await Promise.all([this.loadPubs(), this.loadStatus(), this.loadList()])
        return r
      } finally { this.publishing = false }
    },

    // 轮询工作流 run 到终态 → 映射成向导结果行。超时/异常直接抛（见 publish 注释）
    async _pollWorkflowRows(runId, platforms) {
      const deadline = Date.now() + 300000     // 5 分钟硬顶（平台间风控 sleep 8-20s/台）
      let run = null
      while (Date.now() < deadline) {
        run = await api.runDetail(runId)
        if (['done', 'failed', 'waiting_human'].includes(run.status)) break
        await new Promise(res => setTimeout(res, 2000))
      }
      this.loadRuns()
      if (!run || run.status === 'running') throw new Error('工作流发布超时')
      const res = run.result || {}
      if (run.status === 'failed') {
        return (res.results && res.results.length)
          ? res.results
          : platforms.map(p => ({ platform: p, ok: false, error: run.error || '工作流失败' }))
      }
      if (run.status === 'waiting_human') {
        const t = res.human_task || {}
        // 已完成平台的真实结果 + 挂起平台合成 warning 行（对齐向导展示契约）
        return [...(res.results || []),
                { platform: t.platform, ok: true,
                  warning: t.message || '需要人工完成最后一步',
                  edit_url: t.edit_url || '' }]
      }
      return res.results || []
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
