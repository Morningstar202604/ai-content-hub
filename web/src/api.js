import axios from 'axios'
import { ElMessage } from 'element-plus'

// dev 走 vite proxy(/api -> :8800)，生产构建后与 FastAPI 同源
const http = axios.create({
  baseURL: import.meta.env.DEV ? '/api' : '',
  timeout: 120000   // 发布/更新要开浏览器，慢是正常的
})

http.interceptors.response.use(
  r => r.data,
  err => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(err)
  }
)

export default http

export const api = {
  status: () => http.get('/status'),
  platforms: () => http.get('/platforms'),
  accounts: () => http.get('/accounts'),
  checkAccount: (platform, account = 'default') =>
    http.get(`/accounts/${platform}/check`, { params: { account } }),
  // 登录是长任务（等人扫码），异步启动 + 轮询状态
  startLogin: (platform, account = 'default') =>
    http.post(`/accounts/${platform}/login`, { account, timeout: 300 }),
  loginStatus: (platform, taskId) =>
    http.get(`/accounts/${platform}/login/status`, { params: { task_id: taskId } }),
  refresh: (platform) => http.post(`/refresh/${platform}`),

  listArticles: (status) => http.get('/articles', { params: { status } }),
  getArticle: (id) => http.get(`/articles/${id}`),
  createArticle: (data) => http.post('/articles', data),
  updateArticle: (id, data) => http.put(`/articles/${id}`, data),
  search: (kw) => http.get(`/articles/search/${kw}`),

  publish: (id, platforms, draftOnly = false, account = 'default') =>
    http.post(`/articles/${id}/publish`, { platforms, draft_only: draftOnly, account }),
  // 工作流引擎发布（LangGraph，ADR-001）：立即返回 run_id，轮询 runs() 看进度
  publishWorkflow: (id, platforms, draftOnly = false, account = 'default') =>
    http.post(`/articles/${id}/publish/workflow`,
              { platforms, draft_only: draftOnly, account }),
  runs: (limit = 50) => http.get('/runs', { params: { limit } }),
  runDetail: (runId) => http.get(`/runs/${runId}`),
  resumeRun: (runId, approved = true, note = '') =>
    http.post(`/runs/${runId}/resume`, { approved, note }),
  update: (id, platforms, account = 'default') =>
    http.post(`/articles/${id}/update`, { platforms, account }),
  syncPending: () => http.post('/sync/pending'),
  // M5 切流：原地更新/同步走工作流引擎
  updateWorkflow: (id, platforms, account = 'default') =>
    http.post(`/articles/${id}/update/workflow`, { platforms, account }),
  syncPendingWorkflow: (account = 'default') =>
    http.post('/sync/pending/workflow', { account }),
  // 人工步骤接管：带登录态的内置有头浏览器打开平台页
  assistOpen: (platform, url) =>
    http.post(`/accounts/${platform}/assist`, { url }),
  assistStatus: (platform, taskId) =>
    http.get(`/accounts/${platform}/assist/status`, { params: { task_id: taskId } }),
  publications: (articleId) => http.get('/publications', { params: { article_id: articleId } }),
  // 需要人工处理的发布实例（掘金草稿等人点"确定并发布"）
  pendingHuman: () => http.get('/pending-human'),

  aiWrite: (data) => http.post('/ai/write', data),
  aiRewrite: (id, instruction, publishTo) =>
    http.post(`/articles/${id}/ai-rewrite`, { instruction, publish_to: publishTo }),
  aiPolish: (id) => http.post(`/articles/${id}/ai-polish`),
  aiStatus: () => http.get('/ai/status'),

  jobs: () => http.get('/jobs')
}
