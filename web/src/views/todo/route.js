import i18n from '~/i18n'
const { t } = i18n.global

const Layout = () => import('@/layout/index.vue')

export default {
    name: 'Todo',
    path: '/todo',
    component: Layout,
    redirect: '/todo/quadrant',
    meta: {
        title: '待办事项',
        icon: 'icon-park-outline:task-list',
        order: 3,
        roles: ['admin', 'user'], // 允许访问的角色
        permissions: ['todo:view'] // 需要的权限
    },
    children: [
        {
            name: 'TodoQuadrant',
            path: 'quadrant',
            component: () => import('./TodoQuadrant.vue'),
            meta: {
                title: '四象限待办',
                icon: 'icon-park-outline:grid-four',
                keepAlive: true,
                roles: ['admin', 'user'],
                permissions: ['todo:view']
            }
        },
        {
            name: 'TodoStatistics',
            path: 'statistics',
            component: () => import('./TodoStatistics.vue'),
            meta: {
                title: '待办统计',
                icon: 'icon-park-outline:chart-line',
                keepAlive: true,
                roles: ['admin', 'user'],
                permissions: ['todo:view']
            }
        }
    ]
} 