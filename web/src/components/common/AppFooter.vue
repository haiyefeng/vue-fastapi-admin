<template>
  <footer class="f-c-c flex-col py-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-dark">
    <div class="text-center">
      <a href="https://beian.miit.gov.cn" target="_blank" rel="noopener noreferrer" class="text-gray-500 hover:text-primary transition-colors duration-300 flex items-center justify-center">
        <icon-custom-shield class="mr-1 text-16" />
        粤ICP备2025400737号
      </a>
    </div>
    <div class="mt-2 text-12 text-gray-400">
      © {{ new Date().getFullYear() }} Kaizen Journal. All Rights Reserved.
    </div>
  </footer>
</template>

<script setup>
import { defineComponent, h } from 'vue'

// 自定义盾牌图标组件
const IconCustomShield = defineComponent({
  name: 'IconCustomShield',
  render() {
    return h('svg', {
      viewBox: '0 0 24 24',
      width: '1em',
      height: '1em',
      fill: 'currentColor'
    }, [
      h('path', {
        d: 'M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 4c1.86 0 3.41 1.28 3.86 3H8.14c.45-1.72 2-3 3.86-3zm0 14.75c-3.75-.89-6.5-4.49-6.5-8.25h13c0 3.76-2.75 7.36-6.5 8.25z'
      })
    ])
  }
})
</script>
