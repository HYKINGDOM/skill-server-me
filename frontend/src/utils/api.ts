import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

// 创建 axios 实例
export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response
  },
  async (error) => {
    const { response, config } = error

    // 401 未授权
    if (response?.status === 401) {
      const authStore = useAuthStore()
      
      // 尝试刷新 token
      const refreshToken = localStorage.getItem('refreshToken')
      if (refreshToken && !config._retry) {
        config._retry = true
        try {
          const refreshResponse = await axios.post('/api/auth/refresh', null, {
            params: { refresh_token: refreshToken },
          })
          const newToken = refreshResponse.data.access_token
          localStorage.setItem('token', newToken)
          config.headers.Authorization = `Bearer ${newToken}`
          return api(config)
        } catch (refreshError) {
          authStore.logout()
          router.push('/login')
          ElMessage.error('登录已过期，请重新登录')
          return Promise.reject(refreshError)
        }
      } else {
        authStore.logout()
        router.push('/login')
        ElMessage.error('请先登录')
      }
    }

    // 403 禁止访问
    if (response?.status === 403) {
      ElMessage.error('权限不足')
    }

    // 404 未找到
    if (response?.status === 404) {
      ElMessage.error('资源不存在')
    }

    // 500 服务器错误
    if (response?.status >= 500) {
      ElMessage.error('服务器错误，请稍后重试')
    }

    // 业务错误
    if (response?.data?.message) {
      ElMessage.error(response.data.message)
    }

    return Promise.reject(error)
  }
)

// 文件上传
export const uploadFile = async (url: string, file: File, data?: Record<string, string>) => {
  const formData = new FormData()
  formData.append('file', file)
  
  if (data) {
    Object.entries(data).forEach(([key, value]) => {
      formData.append(key, value)
    })
  }

  return api.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

// 下载文件
export const downloadFile = async (url: string, filename: string) => {
  const response = await api.get(url, {
    responseType: 'blob',
  })
  
  const blob = new Blob([response.data])
  const downloadUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(downloadUrl)
}
