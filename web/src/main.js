import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as Icons from '@element-plus/icons-vue'

import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './styles/main.scss'

import App from './App.vue'

const app = createApp(App)

// 全量注册图标，模板里 <el-icon><Plus/></el-icon> 直接能用
for (const [key, comp] of Object.entries(Icons)) {
  app.component(key, comp)
}

app.use(createPinia())
app.use(ElementPlus, { locale: zhCn, size: 'default' })
app.mount('#app')
