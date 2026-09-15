<template>
  <div class="empty-brand" :style="{ '--esz': px + 'px' }">
    <svg viewBox="0 0 48 48" class="illu" aria-hidden="true">
      <!-- 极简线性图标：文件 + 发射箭头，单色 -->
      <rect x="9" y="7" width="22" height="28" rx="3"
            fill="none" stroke="var(--line-strong)" stroke-width="1.6" />
      <line x1="14" y1="16" x2="26" y2="16" stroke="var(--tx-4)" stroke-width="1.6" stroke-linecap="round" />
      <line x1="14" y1="21" x2="24" y2="21" stroke="var(--tx-4)" stroke-width="1.6" stroke-linecap="round" />
      <line x1="14" y1="26" x2="20" y2="26" stroke="var(--tx-4)" stroke-width="1.6" stroke-linecap="round" />
      <path d="M31 20 L42 26 L31 32 L33 26 Z"
            fill="none" stroke="var(--tx-3)" stroke-width="1.6" stroke-linejoin="round" />
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
  px: { type: Number, default: 44 }
})
</script>

<style scoped>
.empty-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 36px 16px;
  text-align: center;
  animation: fadeUp .3s var(--ease-out) both;
}
.illu {
  width: var(--esz, 44px);
  height: auto;
  margin-bottom: 12px;
  opacity: .9;
}
.tt {
  margin: 0;
  font-size: var(--fs-md);
  font-weight: 500;
  color: var(--tx-2);
}
.dd {
  margin: 5px 0 0;
  font-size: var(--fs-sm);
  color: var(--tx-3);
  max-width: 220px;
  line-height: 1.6;
}
:deep(.el-button) { margin-top: 14px; }
</style>
