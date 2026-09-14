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
  update: (id, platforms, account = 'default') =>
    http.post(`/articles/${id}/update`, { platforms, account }),
  syncPending: () => http.post('/sync/pending'),
  publications: (articleId) => http.get('/publications', { params: { article_id: articleId } }),

  aiWrite: (data) => http.post('/ai/write', data),
  aiRewrite: (id, instruction, publishTo) =>
    http.post(`/articles/${id}/ai-rewrite`, { instruction, publish_to: publishTo }),
  aiPolish: (id) => http.post(`/articles/${id}/ai-polish`),
  aiStatus: () => http.get('/ai/status'),

  jobs: () => http.get('/jobs')
}
