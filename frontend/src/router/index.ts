import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { 
  setCurrentRouteKey, 
  cancelRouteRequests
} from '@/utils/api'

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

// ==================== 路由守卫 ====================

/**
 * 生成路由标识
 * 用于标识当前路由的请求
 * @param path 路由路径
 * @returns 路由标识
 */
function generateRouteKey(path: string): string {
  // 使用路径作为路由标识，移除动态参数以避免重复
  const basePath = path.split('/').slice(0, 3).join('/')
  return `route_${basePath.replace(/\//g, '_')}`
}

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  // ==================== 请求取消逻辑 ====================
  
  // 如果是从一个路由切换到另一个路由，取消前一个路由的请求
  if (_from.path && _from.path !== to.path) {
    const fromRouteKey = generateRouteKey(_from.path)
    
    // 取消前一个路由的所有未完成请求
    cancelRouteRequests(fromRouteKey, `路由从 ${_from.path} 切换到 ${to.path}`)
  }

  // 设置当前路由标识
  const currentRouteKey = generateRouteKey(to.path)
  setCurrentRouteKey(currentRouteKey)

  // ==================== 页面标题设置 ====================
  
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - Skills Hub` : 'Skills Hub'

  // ==================== 认证检查 ====================
  
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

  // ==================== 权限检查 ====================
  
  // 检查管理员权限
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next({ name: 'SkillList' })
    return
  }

  next()
})

/**
 * 路由后置守卫
 * 用于清理和统计
 */
router.afterEach((_to, _from) => {
  // 可以在这里添加页面访问统计等逻辑
  // console.log(`路由切换完成: ${_from.path} -> ${to.path}`)
})

/**
 * 路由错误处理
 */
router.onError((error) => {
  console.error('路由错误:', error)
})

export default router
