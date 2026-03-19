import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/utils/api'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refreshToken'))

  // 计算属性
  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.system_role === 'admin')
  const username = computed(() => user.value?.username || '')

  // 方法
  async function login(username: string, password: string) {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)

    const response = await api.post('/auth/login', {
      username,
      password,
    })

    const data = response.data
    token.value = data.access_token
    refreshToken.value = data.refresh_token

    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refreshToken', data.refresh_token)

    // 获取用户信息
    await fetchUserInfo()

    return data
  }

  async function fetchUserInfo() {
    if (!token.value) return

    try {
      const response = await api.get('/auth/me')
      user.value = response.data
    } catch (error) {
      logout()
      throw error
    }
  }

  async function checkAuth() {
    if (token.value) {
      try {
        await fetchUserInfo()
      } catch (error) {
        // Token 无效，尝试刷新
        if (refreshToken.value) {
          try {
            const response = await api.post('/auth/refresh', null, {
              params: { refresh_token: refreshToken.value },
            })
            token.value = response.data.access_token
            refreshToken.value = response.data.refresh_token
            localStorage.setItem('token', response.data.access_token)
            localStorage.setItem('refreshToken', response.data.refresh_token)
            await fetchUserInfo()
          } catch (refreshError) {
            logout()
          }
        } else {
          logout()
        }
      }
    }
  }

  function logout() {
    user.value = null
    token.value = null
    refreshToken.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await api.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  }

  return {
    user,
    token,
    refreshToken,
    isLoggedIn,
    isAdmin,
    username,
    login,
    logout,
    checkAuth,
    fetchUserInfo,
    changePassword,
  }
})
