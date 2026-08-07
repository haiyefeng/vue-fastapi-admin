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
        <li v-for="project in group.projects" :key="project.id" class="nav-item">
          <a
            href="javascript:;"
            :class="{ active: isProjectActive(project.id) }"
            @click="selectProject(project)"
          >
            {{ project.name }}
          </a>
          <n-dropdown
            trigger="click"
            :options="activeProjectOptions"
            @select="(key) => handleProjectAction(key, project)"
          >
            <button class="nav-item-more" @click.stop>⋯</button>
          </n-dropdown>
        </li>
      </ul>
    </template>

    <n-collapse v-if="archivedProjects.length" class="archived-collapse">
      <n-collapse-item title="已归档" name="archived">
        <ul class="nav-list">
          <li v-for="project in archivedProjects" :key="project.id" class="nav-item">
            <a
              href="javascript:;"
              :class="{ active: isProjectActive(project.id) }"
              @click="selectProject(project)"
            >
              {{ project.name }}
            </a>
            <n-dropdown
              trigger="click"
              :options="archivedProjectOptions"
              @select="(key) => handleProjectAction(key, project)"
            >
              <button class="nav-item-more" @click.stop>⋯</button>
            </n-dropdown>
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
import { useMessage, useDialog } from 'naive-ui'
import api from '@/api'
import NewProjectModal from './NewProjectModal.vue'

const emit = defineEmits(['select', 'changed'])

const message = useMessage()
const dialog = useDialog()

const activeProjectOptions = [
  { label: '归档', key: 'archive' },
  { label: '删除', key: 'delete' },
]
const archivedProjectOptions = [
  { label: '取消归档', key: 'unarchive' },
  { label: '删除', key: 'delete' },
]

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
const isProjectActive = (id) =>
  activeSelection.value.type === 'project' && activeSelection.value.id === id

const fetchProjects = async () => {
  try {
    const res = await api.getProjects()
    projects.value = res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
    message.error('获取项目列表失败')
  }
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

const setArchived = async (project, isArchived) => {
  try {
    await api.updateProject(project.id, { is_archived: isArchived })
    await fetchProjects()
    emit('changed')
  } catch (error) {
    console.error('更新项目失败:', error)
    message.error('更新项目失败')
  }
}

const deleteProject = (project) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除项目「${project.name}」吗？项目内的任务将退回收件箱，不会被删除。`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deleteProject(project.id)
        message.success('删除成功')
        await fetchProjects()
        emit('changed')
        if (isProjectActive(project.id)) {
          selectInbox()
        }
      } catch (error) {
        console.error('删除项目失败:', error)
        message.error('删除失败')
      }
    },
  })
}

const handleProjectAction = (key, project) => {
  if (key === 'archive') {
    setArchived(project, true)
  } else if (key === 'unarchive') {
    setArchived(project, false)
  } else if (key === 'delete') {
    deleteProject(project)
  }
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav-list a.active {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
  font-weight: 500;
}
.nav-item {
  display: flex;
  align-items: center;
}
.nav-item a {
  flex: 1;
  min-width: 0;
}
.nav-item-more {
  flex-shrink: 0;
  visibility: hidden;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.2em 0.5em;
  margin-right: 0.4em;
  border-radius: 4px;
  color: inherit;
  opacity: 0.6;
  line-height: 1;
}
.nav-item:hover .nav-item-more {
  visibility: visible;
}
.nav-item-more:hover {
  opacity: 1;
  background: rgba(128, 128, 128, 0.15);
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
