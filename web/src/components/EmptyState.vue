<template>
  <div class="empty-brand" :style="{ '--esz': px + 'px' }">
    <svg viewBox="0 0 140 110" class="illu" aria-hidden="true">
      <defs>
        <linearGradient id="es-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#6D5CFF" />
          <stop offset="1" stop-color="#C44BFF" />
        </linearGradient>
      </defs>
      <!-- 虚线轨道 -->
      <ellipse cx="70" cy="66" rx="52" ry="20" fill="none" stroke="#2A3145" stroke-width="1.6"
               stroke-dasharray="5 6" stroke-linecap="round" />
      <!-- 发射台平台 -->
      <rect x="46" y="72" width="48" height="5" rx="2.5" fill="#1C2230" />
      <rect x="52" y="77" width="36" height="3" rx="1.5" fill="#171C29" />
      <!-- 纸飞机（悬浮） -->
      <g class="plane">
        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"
              transform="translate(48 22) rotate(10) scale(1.15)" fill="url(#es-g)" />
        <path d="M96 34 L112 28 L100 40 Z" fill="#6D5CFF" opacity=".35" />
        <circle cx="112" cy="27" r="2.2" fill="#C44BFF" opacity=".8" />
        <circle cx="119" cy="22" r="1.5" fill="#9B4DFF" opacity=".5" />
        <circle cx="125" cy="17" r="1" fill="#C44BFF" opacity=".3" />
      </g>
      <!-- 星点 -->
      <circle cx="30" cy="28" r="1.6" fill="#3A4460" />
      <circle cx="116" cy="52" r="1.4" fill="#3A4460" />
      <circle cx="22" cy="60" r="1.2" fill="#3A4460" />
    </svg>
    <p class="tt">{{ title }}</p>
    <p v-if="desc" class="dd">{{ desc }}</p>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '空空如也' },
  desc: { type: String, default: '' },
  px: { type: Number, default: 128 }
})
</script>

<style scoped>
.empty-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 34px 16px;
  text-align: center;
  animation: fadeUp .4s var(--ease-out) both;
}
.illu {
  width: var(--esz, 128px);
  height: auto;
  margin-bottom: 6px;
  animation: floaty 4.5s ease-in-out infinite;
}
.plane { transform-origin: 70px 40px; }
.tt {
  margin: 2px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}
.dd {
  margin: 5px 0 0;
  font-size: 11.5px;
  color: var(--el-text-color-placeholder);
  max-width: 240px;
  line-height: 1.6;
}
</style>
