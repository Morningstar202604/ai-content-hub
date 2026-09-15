<template>
  <span class="brand" :class="{ big: size === 'big' }">
    <svg class="brand-mark" :style="{ width: px + 'px', height: px + 'px' }" viewBox="0 0 48 48" aria-hidden="true">
      <!-- 极简 mark：圆角方块 + 白色纸飞机，无渐变 -->
      <rect x="2" y="2" width="44" height="44" rx="11" fill="var(--tx-1)" />
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"
            transform="translate(12.6 13) rotate(8 12 12)" fill="var(--bg)" />
      <!-- 尾迹三点：暗示多平台分发 -->
      <circle cx="11" cy="38" r="1.5" :fill="`var(--bg)`" opacity=".75" />
      <circle cx="16.5" cy="40" r="1.1" fill="var(--bg)" opacity=".45" />
      <circle cx="21.5" cy="41.2" r=".9" fill="var(--bg)" opacity=".25" />
    </svg>
    <span v-if="withName" class="brand-txt">
      <span class="brand-name">{{ name }}</span>
      <span v-if="sub" class="brand-sub">{{ sub }}</span>
    </span>
  </span>
</template>

<script setup>
defineProps({
  name: { type: String, default: '一稿' },
  sub: { type: String, default: '一稿写 · 全网发' },
  px: { type: Number, default: 28 },
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
  font-size: 14px;
  font-weight: 650;
  letter-spacing: .02em;
  line-height: 1;
  color: var(--tx-1);
}
.brand-sub {
  font-size: 10px;
  color: var(--tx-3);
  letter-spacing: .06em;
  margin-top: 3px;
  line-height: 1;
  white-space: nowrap;
}
</style>
