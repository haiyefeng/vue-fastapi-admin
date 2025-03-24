<template>
  <AppProvider>
    <todoStatistics />
    <router-view v-slot="{ Component }">
      <component :is="Component" />
    </router-view>
  </AppProvider>
</template>

<script setup>
import AppProvider from '@/components/common/AppProvider.vue'
import todoStatistics from '@/views/todo/TodoStatistics.vue'
</script>
