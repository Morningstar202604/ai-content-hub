<template>
  <span class="brand" :class="{ big: size === 'big' }">
    <svg class="brand-mark" :style="{ width: px + 'px', height: px + 'px' }" viewBox="0 0 48 48" aria-hidden="true">
      <defs>
        <linearGradient :id="gid" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#6D5CFF" />
          <stop offset=".55" stop-color="#9B4DFF" />
          <stop offset="1" stop-color="#C44BFF" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" :fill="`url(#${gid})`" />
      <!-- 对角高光，给 logo 一点玻璃质感 -->
      <rect x="2" y="2" width="44" height="44" fill="url(#hl)" />
      <defs>
        <linearGradient id="hl" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#fff" stop-opacity=".22" />
          <stop offset=".5" stop-color="#fff" stop-opacity="0" />
        </linearGradient>
      </defs>
      <!-- 纸飞机：一稿，发出去 -->
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"
            :transform="`translate(12.6 13) rotate(8 12 12)`" fill="#fff" />
      <!-- 尾迹：多平台分发 -->
      <circle cx="10.5" cy="38.5" r="1.8" fill="#fff" opacity=".9" />
      <circle cx="16.5" cy="40.5" r="1.4" fill="#fff" opacity=".55" />
      <circle cx="21.5" cy="41.8" r="1.1" fill="#fff" opacity=".3" />
    </svg>
    <span v-if="withName" class="brand-txt">
      <span class="brand-name">{{ name }}</span>
      <span v-if="sub" class="brand-sub">{{ sub }}</span>
    </span>
  </span>
</template>

<script>
// 模块级计数器：多实例并存时渐变 id 不撞车
let seq = 0
</script>

<script setup>
const gid = `bg-${++seq}`
const props = defineProps({
  name: { type: String, default: '一稿' },
  sub: { type: String, default: '一稿写 · 全网发' },
  px: { type: Number, default: 30 },
  withName: { type: Boolean, default: true },
  size: { type: String, default: '' }
})
</script>

<style scoped>
.brand {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  user-select: none;
}
.brand-txt { display: flex; flex-direction: column; }
.brand-name {
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 1px;
  line-height: 1;
  background: linear-gradient(100deg, #EDEAFF 10%, #B9A8FF 55%, #E39BFF 95%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.brand-sub {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  letter-spacing: 2px;
  margin-top: 3px;
  line-height: 1;
  white-space: nowrap;
}
</style>
