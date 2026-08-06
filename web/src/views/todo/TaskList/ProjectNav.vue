<template>
  <nav class="project-nav">
    <ul class="nav-list">
      <li>
        <a href="javascript:;" :class="{ active: isInboxActive }" @click="selectInbox">收件箱</a>
      </li>
    </ul>

    <template v-for="group in groupedProjects" :key="group.name">
      <div class="nav-group">{{ group.name }}</div>
      <ul class="nav-list">
        <li v-for="project in group.projects" :key="project.id">
          <a href="javascript:;" :class="{ active: isProjectActive(project.id) }" @click="selectProject(project)">
            {{ project.name }}
          </a>
        </li>
      </ul>
    </template>

    <n-collapse v-if="archivedProjects.length" class="archived-collapse">
      <n-collapse-item title="已归档" name="archived">
        <ul class="nav-list">
          <li v-for="project in archivedProjects" :key="project.id">
            <a href="javascript:;" :class="{ active: isProjectActive(project.id) }" @click="selectProject(project)">
              {{ project.name }}
            </a>
          </li>
        </ul>
      </n-collapse-item>
    </n-collapse>

    <ul class="nav-list create-entry">
      <li>
        <a href="javascript:;" @click="showCreateModal = true">+ 新建项目/清单</a>
      </li>
    </ul>

    <NewProjectModal v-model:show="showCreateModal" @created="handleCreated" />
  </nav>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/api'
import NewProjectModal from './NewProjectModal.vue'

const emit = defineEmits(['select', 'changed'])

const projects = ref([])
const activeSelection = ref({ type: 'inbox' })
const showCreateModal = ref(false)

const activeProjects = computed(() => projects.value.filter((p) => !p.is_archived))
const archivedProjects = computed(() => projects.value.filter((p) => p.is_archived))

const groupedProjects = computed(() => {
  const groups = new Map()
  for (const project of activeProjects.value) {
    const key = project.category_name || '未分组'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(project)
  }
  return Array.from(groups.entries()).map(([name, list]) => ({ name, projects: list }))
})

const isInboxActive = computed(() => activeSelection.value.type === 'inbox')
const isProjectActive = (id) => activeSelection.value.type === 'project' && activeSelection.value.id === id

const fetchProjects = async () => {
  const res = await api.getProjects()
  projects.value = res.data || []
}

const selectInbox = () => {
  activeSelection.value = { type: 'inbox' }
  emit('select', { type: 'inbox' })
}

const selectProject = (project) => {
  activeSelection.value = { type: 'project', id: project.id }
  emit('select', { type: 'project', id: project.id, name: project.name })
}

const handleCreated = async (project) => {
  await fetchProjects()
  emit('changed')
  selectProject(project)
}

defineExpose({ refresh: fetchProjects })

onMounted(async () => {
  await fetchProjects()
  selectInbox()
})
</script>

<style scoped>
.project-nav {
  width: 200px;
  flex-shrink: 0;
}
.nav-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.nav-list a {
  display: block;
  padding: 0.45em 1em;
  text-decoration: none;
  font-size: 0.92em;
  border-radius: 4px;
  color: inherit;
}
.nav-list a.active {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
  font-weight: 500;
}
.nav-group {
  font-size: 0.8em;
  font-weight: 600;
  padding: 0.8em 1em 0.3em;
  opacity: 0.7;
}
.create-entry {
  margin-top: 0.6em;
  border-top: 1px solid rgba(128, 128, 128, 0.2);
  padding-top: 0.6em;
}
.archived-collapse {
  margin: 0.6em 0.4em;
}
</style>
