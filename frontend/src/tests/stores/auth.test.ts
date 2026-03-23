import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/utils/api'
import { createPinia, setActivePinia } from 'pinia'

// 模拟 localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    }
  }
})()

Object.defineProperty(window, 'localStorage', { value: localStorageMock })

describe('Auth Store', () => {
  let authStore: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    // 清除 localStorage
    localStorageMock.clear()
    // 重置 API 模拟
    vi.resetAllMocks()
    // 创建 Pinia 实例并激活
    const pinia = createPinia()
    setActivePinia(pinia)
    // 创建新的 store 实例
    authStore = useAuthStore()
  })

  describe('login', () => {
    it('should login successfully and set tokens', async () => {
      // 模拟 API 响应
      const mockResponse = {
        data: {
          access_token: 'test-token',
          refresh_token: 'test-refresh-token'
        }
      }

      const mockUserInfo = {
        data: {
          id: '1',
          username: 'test-user',
          email: 'test@example.com',
          system_role: 'user',
          is_active: true,
          created_at: '2023-01-01T00:00:00Z'
        }
      }

      vi.spyOn(api, 'post').mockResolvedValueOnce(mockResponse)
      vi.spyOn(api, 'get').mockResolvedValueOnce(mockUserInfo)

      // 执行登录
      const result = await authStore.login('test-user', 'test-password')

      // 验证结果
      expect(result).toEqual(mockResponse.data)
      expect(authStore.token).toBe('test-token')
      expect(authStore.refreshToken).toBe('test-refresh-token')
      expect(authStore.user).toEqual(mockUserInfo.data)
      expect(authStore.isLoggedIn).toBe(true)
      expect(localStorage.getItem('token')).toBe('test-token')
      expect(localStorage.getItem('refreshToken')).toBe('test-refresh-token')
    })

    it('should throw error on login failure', async () => {
      // 模拟 API 错误
      const mockError = new Error('Login failed')
      vi.spyOn(api, 'post').mockRejectedValueOnce(mockError)

      // 执行登录并验证错误
      await expect(authStore.login('test-user', 'test-password')).rejects.toThrow('Login failed')
    })
  })

  describe('logout', () => {
    it('should clear all auth data', () => {
      // 先设置一些数据
      authStore.token = 'test-token'
      authStore.refreshToken = 'test-refresh-token'
      authStore.user = {
        id: '1',
        username: 'test-user',
        email: 'test@example.com',
        system_role: 'user',
        is_active: true,
        created_at: '2023-01-01T00:00:00Z'
      }

      // 执行登出
      authStore.logout()

      // 验证数据已清除
      expect(authStore.token).toBe(null)
      expect(authStore.refreshToken).toBe(null)
      expect(authStore.user).toBe(null)
      expect(authStore.isLoggedIn).toBe(false)
      expect(localStorage.getItem('token')).toBe(null)
      expect(localStorage.getItem('refreshToken')).toBe(null)
    })
  })

  describe('isAdmin', () => {
    it('should return true when user is admin', () => {
      authStore.user = {
        id: '1',
        username: 'admin',
        email: 'admin@example.com',
        system_role: 'admin',
        is_active: true,
        created_at: '2023-01-01T00:00:00Z'
      }
      expect(authStore.isAdmin).toBe(true)
    })

    it('should return false when user is not admin', () => {
      authStore.user = {
        id: '1',
        username: 'user',
        email: 'user@example.com',
        system_role: 'user',
        is_active: true,
        created_at: '2023-01-01T00:00:00Z'
      }
      expect(authStore.isAdmin).toBe(false)
    })

    it('should return false when no user', () => {
      authStore.user = null
      expect(authStore.isAdmin).toBe(false)
    })
  })
})
