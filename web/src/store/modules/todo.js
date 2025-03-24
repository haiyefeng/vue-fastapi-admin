import { defineStore } from 'pinia'
import api from '@/api'

export const useTodoStore = defineStore('todo', {
    state: () => ({
        // 待办事项列表
        todoList: [],
        // 分页信息
        pagination: {
            page: 1,
            page_size: 10,
            total: 0
        },
        // 筛选条件
        filters: {
            quadrant_type: null,
            is_completed: null,
            start_date: null,
            end_date: null
        },
        // 统计数据
        statistics: {
            daily: [],
            quadrant: {
                urgent_important: 0,
                urgent_not_important: 0,
                important_not_urgent: 0,
                not_urgent_not_important: 0
            }
        },
        // 加载状态
        loading: false
    }),

    getters: {
        // 按象限分组的待办事项
        todosByQuadrant: (state) => {
            const grouped = {
                urgent_important: [],
                urgent_not_important: [],
                important_not_urgent: [],
                not_urgent_not_important: []
            }

            state.todoList.forEach(todo => {
                grouped[todo.quadrant_type.toLowerCase()].push(todo)
            })

            return grouped
        },

        // 已完成的待办事项
        completedTodos: (state) => {
            return state.todoList.filter(todo => todo.is_completed)
        },

        // 未完成的待办事项
        uncompletedTodos: (state) => {
            return state.todoList.filter(todo => !todo.is_completed)
        }
    },

    actions: {
        // 获取待办事项列表
        async fetchTodos(params = {}) {
            this.loading = true
            try {
                const response = await api.getTodos({
                    ...this.pagination,
                    ...this.filters,
                    ...params
                })
                this.todoList = response.data
                this.pagination.total = response.total
            } finally {
                this.loading = false
            }
        },

        // 创建待办事项
        async createTodo(todoData) {
            try {
                const response = await api.createTodo(todoData)
                this.todoList.unshift(response)
                return response
            } catch (error) {
                throw error
            }
        },

        // 更新待办事项
        async updateTodo(id, todoData) {
            try {
                const response = await api.updateTodo(id, todoData)
                const index = this.todoList.findIndex(todo => todo.id === id)
                if (index !== -1) {
                    this.todoList[index] = response
                }
                return response
            } catch (error) {
                throw error
            }
        },

        // 删除待办事项
        async deleteTodo(id) {
            try {
                await api.deleteTodo(id)
                this.todoList = this.todoList.filter(todo => todo.id !== id)
            } catch (error) {
                throw error
            }
        },

        // 获取统计数据
        async fetchStatistics() {
            try {
                const [dailyStats, quadrantStats] = await Promise.all([
                    api.getDailyStatistics(this.filters),
                    api.getQuadrantStatistics()
                ])
                this.statistics.daily = dailyStats
                this.statistics.quadrant = quadrantStats
            } catch (error) {
                throw error
            }
        },

        // 更新筛选条件
        updateFilters(filters) {
            this.filters = {
                ...this.filters,
                ...filters
            }
        },

        // 重置状态
        resetState() {
            this.$reset()
        }
    }
}) 