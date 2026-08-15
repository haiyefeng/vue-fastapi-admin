<template>
  <div class="empty-state">
    <div class="empty-state-icon"><TheIcon :icon="icon" :size="18" /></div>
    <div class="empty-state-text">{{ text }}</div>
    <n-button
      v-if="linkText && to"
      text
      type="primary"
      class="empty-state-link"
      @click="router.push(to)"
    >
      {{ linkText }}
      <template #icon><TheIcon icon="material-symbols:arrow-forward" :size="12" /></template>
    </n-button>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import TheIcon from '@/components/icon/TheIcon.vue'

defineProps({
  icon: { type: String, required: true },
  text: { type: String, required: true },
  linkText: { type: String, default: '' },
  to: { type: String, default: '' },
})

const router = useRouter()
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 28px 10px 14px;
  color: var(--dt-ink-faint);
}
.empty-state-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--dt-radius-md);
  background: var(--dt-page-bg);
  border: 1px dashed var(--dt-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dt-ink-faint);
  margin-bottom: 10px;
}
.empty-state-text {
  font-size: 12.5px;
  margin-bottom: 10px;
}
.empty-state-link {
  font-size: 12px;
}
</style>
