import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/skills',
      },
      {
        path: 'skills',
        name: 'SkillList',
        component: () => import('@/views/skills/SkillList.vue'),
        meta: { title: 'Skill 列表' },
      },
      {
        path: 'skills/create',
        name: 'SkillCreate',
        component: () => import('@/views/skills/SkillCreate.vue'),
        meta: { title: '创建 Skill' },
      },
      {
        path: 'skills/:id',
        name: 'SkillDetail',
        component: () => import('@/views/skills/SkillDetail.vue'),
        meta: { title: 'Skill 详情' },
      },
      {
        path: 'skills/:id/edit',
        name: 'SkillEdit',
        component: () => import('@/views/skills/SkillEdit.vue'),
        meta: { title: '编辑 Skill' },
      },
      {
        path: 'repos',
        name: 'RepoList',
        component: () => import('@/views/repos/RepoList.vue'),
        meta: { title: 'Git 仓库' },
      },
      {
        path: 'search',
        name: 'Search',
        component: () => import('@/views/Search.vue'),
        meta: { title: '搜索' },
      },
      {
        path: 'favorites',
        name: 'Favorites',
        component: () => import('@/views/Favorites.vue'),
        meta: { title: '我的收藏' },
      },
      {
        path: 'notifications',
        name: 'Notifications',
        component: () => import('@/views/Notifications.vue'),
        meta: { title: '通知中心' },
      },
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/Admin.vue'),
        meta: { title: '系统管理', requiresAdmin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - Skills Hub` : 'Skills Hub'

  // 不需要认证的页面
  if (to.meta.requiresAuth === false) {
    next()
    return
  }

  // 检查是否已登录
  if (!authStore.isLoggedIn) {
    // 尝试从本地存储恢复登录状态
    await authStore.checkAuth()
  }

  if (!authStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  // 检查管理员权限
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next({ name: 'SkillList' })
    return
  }

  next()
})

export default router
