import axios, { type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

// ==================== 错误响应类型定义 ====================

/**
 * 统一的错误响应类型
 * 支持多种后端错误格式
 */
export interface ApiErrorResponse {
  // FastAPI 默认格式
  detail?: string
  // 通用消息格式
  message?: string
  // 错误字段
  error?: string
  // 错误代码
  code?: string
  // 错误数据
  data?: unknown
  // 验证错误列表
  errors?: Array<{
    field: string
    message: string
  }>
}

/**
 * 标准化的错误信息
 */
export interface NormalizedError {
  message: string
  code?: string
  status?: number
  data?: unknown
}

// ==================== 请求取消管理器 ====================

/**
 * 请求取消管理器类
 * 用于管理路由切换时的请求取消
 */
class RequestCancellationManager {
  // 存储当前路由的 AbortController 映射
  private controllers: Map<string, AbortController> = new Map()
  // 存储每个路由的请求计数
  private requestCounts: Map<string, number> = new Map()

  /**
   * 创建或获取当前路由的 AbortController
   * @param routeKey 路由标识
   * @returns AbortController 实例
   */
  createController(routeKey: string): AbortController {
    // 如果已存在控制器，先取消之前的请求
    if (this.controllers.has(routeKey)) {
      const existingController = this.controllers.get(routeKey)
      existingController?.abort()
    }

    // 创建新的 AbortController
    const controller = new AbortController()
    this.controllers.set(routeKey, controller)
    
    // 增加请求计数
    const count = this.requestCounts.get(routeKey) || 0
    this.requestCounts.set(routeKey, count + 1)

    return controller
  }

  /**
   * 获取当前路由的 AbortController
   * @param routeKey 路由标识
   * @returns AbortController 实例或 undefined
   */
  getController(routeKey: string): AbortController | undefined {
    return this.controllers.get(routeKey)
  }

  /**
   * 取消指定路由的所有请求
   * @param routeKey 路由标识
   * @param reason 取消原因
   */
  cancelRequests(routeKey: string, reason?: string): void {
    const controller = this.controllers.get(routeKey)
    if (controller && !controller.signal.aborted) {
      controller.abort(reason || '路由切换，取消请求')
      this.controllers.delete(routeKey)
      this.requestCounts.delete(routeKey)
    }
  }

  /**
   * 取消所有请求
   * @param reason 取消原因
   */
  cancelAllRequests(reason?: string): void {
    this.controllers.forEach((controller) => {
      if (!controller.signal.aborted) {
        controller.abort(reason || '取消所有请求')
      }
    })
    this.controllers.clear()
    this.requestCounts.clear()
  }

  /**
   * 清理已完成的请求
   * @param routeKey 路由标识
   */
  cleanupCompletedRequest(routeKey: string): void {
    const count = this.requestCounts.get(routeKey) || 0
    if (count > 0) {
      this.requestCounts.set(routeKey, count - 1)
    }
    
    // 如果该路由没有正在进行的请求，清理控制器
    if (count <= 1) {
      this.controllers.delete(routeKey)
      this.requestCounts.delete(routeKey)
    }
  }

  /**
   * 获取当前活跃的请求数量
   */
  getActiveRequestCount(): number {
    let total = 0
    this.requestCounts.forEach((count) => {
      total += count
    })
    return total
  }
}

// 导出请求取消管理器实例
export const requestCancellationManager = new RequestCancellationManager()

// 当前路由标识
let currentRouteKey = ''

/**
 * 设置当前路由标识
 * @param routeKey 路由标识
 */
export function setCurrentRouteKey(routeKey: string): void {
  currentRouteKey = routeKey
}

/**
 * 获取当前路由标识
 */
export function getCurrentRouteKey(): string {
  return currentRouteKey
}

// ==================== 错误处理工具函数 ====================

/**
 * 解析错误响应，提取错误信息
 * @param error 错误对象
 * @returns 标准化的错误信息
 */
export function normalizeError(error: unknown): NormalizedError {
  // 如果是 Axios 错误
  if (axios.isAxiosError(error)) {
    const response = error.response
    const status = response?.status

    // 网络错误
    if (!response) {
      return {
        message: '网络连接失败，请检查网络设置',
        code: 'NETWORK_ERROR',
      }
    }

    // 请求被取消
    if (error.code === 'ERR_CANCELED' || error.name === 'CanceledError') {
      return {
        message: '请求已取消',
        code: 'REQUEST_CANCELED',
        status,
      }
    }

    // 解析响应数据
    const data = response.data as ApiErrorResponse | undefined

    // 提取错误信息（支持多种格式）
    let message = '请求失败'
    
    if (data) {
      // 优先级：detail > message > error
      if (data.detail) {
        message = data.detail
      } else if (data.message) {
        message = data.message
      } else if (data.error) {
        message = data.error
      }

      // 处理验证错误
      if (data.errors && Array.isArray(data.errors) && data.errors.length > 0) {
        const errorMessages = data.errors.map((e) => `${e.field}: ${e.message}`).join('; ')
        message = errorMessages
      }
    }

    return {
      message,
      code: data?.code,
      status,
      data: data?.data,
    }
  }

  // 其他类型的错误
  if (error instanceof Error) {
    return {
      message: error.message,
    }
  }

  return {
    message: '未知错误',
  }
}

/**
 * 获取友好的错误提示信息
 * @param status HTTP 状态码
 * @param errorData 错误数据
 * @returns 友好的错误提示
 */
function getFriendlyErrorMessage(status: number, errorData?: ApiErrorResponse): string {
  // 根据状态码返回友好提示
  const statusMessages: Record<number, string> = {
    400: '请求参数错误',
    401: '登录已过期，请重新登录',
    403: '权限不足，无法访问',
    404: '请求的资源不存在',
    405: '请求方法不允许',
    408: '请求超时',
    409: '资源冲突',
    422: '数据验证失败',
    429: '请求过于频繁，请稍后再试',
    500: '服务器内部错误',
    502: '网关错误',
    503: '服务暂时不可用',
    504: '网关超时',
  }

  // 如果有具体的错误信息，优先使用
  if (errorData?.detail || errorData?.message || errorData?.error) {
    return errorData.detail || errorData.message || errorData.error || '请求失败'
  }

  return statusMessages[status] || '请求失败，请稍后重试'
}

// ==================== Axios 实例创建 ====================

// 扩展 AxiosRequestConfig 类型，添加自定义属性
interface CustomAxiosRequestConfig extends AxiosRequestConfig {
  _retry?: boolean
  _routeKey?: string
}

// 创建 axios 实例
export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ==================== 请求拦截器 ====================

// 请求拦截器
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 添加 token
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // 为请求添加取消信号（如果存在当前路由的 AbortController）
    const routeKey = currentRouteKey
    if (routeKey) {
      const controller = requestCancellationManager.getController(routeKey)
      if (controller) {
        config.signal = controller.signal
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// ==================== 响应拦截器 ====================

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    // 请求成功，清理请求计数
    const routeKey = currentRouteKey
    if (routeKey) {
      requestCancellationManager.cleanupCompletedRequest(routeKey)
    }
    return response
  },
  async (error) => {
    const { response, config } = error
    const customConfig = config as CustomAxiosRequestConfig

    // 如果请求被取消，不显示错误提示
    if (error.code === 'ERR_CANCELED' || error.name === 'CanceledError') {
      console.log('请求已取消:', error.message)
      return Promise.reject(error)
    }

    // 解析错误数据
    const errorData = response?.data as ApiErrorResponse | undefined

    // 401 未授权
    if (response?.status === 401) {
      const authStore = useAuthStore()
      
      // 尝试刷新 token
      const refreshToken = localStorage.getItem('refreshToken')
      if (refreshToken && !customConfig._retry) {
        customConfig._retry = true
        try {
          const refreshResponse = await axios.post('/api/auth/refresh', null, {
            params: { refresh_token: refreshToken },
          })
          const newToken = refreshResponse.data.access_token
          localStorage.setItem('token', newToken)
          // 确保 headers 对象存在
          if (!customConfig.headers) {
            customConfig.headers = {}
          }
          customConfig.headers.Authorization = `Bearer ${newToken}`
          return api(customConfig)
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
      ElMessage.error(getFriendlyErrorMessage(403, errorData))
    }

    // 404 未找到
    if (response?.status === 404) {
      ElMessage.error(getFriendlyErrorMessage(404, errorData))
    }

    // 422 数据验证失败
    if (response?.status === 422) {
      ElMessage.error(getFriendlyErrorMessage(422, errorData))
    }

    // 429 请求过于频繁
    if (response?.status === 429) {
      ElMessage.error(getFriendlyErrorMessage(429, errorData))
    }

    // 500+ 服务器错误
    if (response?.status && response.status >= 500) {
      ElMessage.error(getFriendlyErrorMessage(response.status, errorData))
    }

    // 其他业务错误（400等）
    if (response?.status && response.status >= 400 && response.status < 500) {
      // 使用统一的错误信息提取
      const normalizedError = normalizeError(error)
      if (normalizedError.message && normalizedError.code !== 'REQUEST_CANCELED') {
        ElMessage.error(normalizedError.message)
      }
    }

    return Promise.reject(error)
  }
)

// ==================== 文件上传下载工具函数 ====================

/**
 * 文件上传
 * @param url 上传地址
 * @param file 要上传的文件
 * @param data 额外的表单数据
 * @returns 上传响应
 */
export const uploadFile = async (url: string, file: File, data?: Record<string, string>) => {
  const formData = new FormData()
  formData.append('file', file)
  
  // 添加额外的表单数据
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

/**
 * 下载文件
 * @param url 下载地址
 * @param filename 保存的文件名
 */
export const downloadFile = async (url: string, filename: string) => {
  const response = await api.get(url, {
    responseType: 'blob',
  })
  
  // 创建 Blob 对象
  const blob = new Blob([response.data])
  const downloadUrl = window.URL.createObjectURL(blob)
  
  // 创建下载链接
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  
  // 清理
  document.body.removeChild(link)
  window.URL.revokeObjectURL(downloadUrl)
}

/**
 * 创建可取消的请求
 * @param routeKey 路由标识
 * @returns AbortController 实例
 */
export const createCancellableRequest = (routeKey: string): AbortController => {
  return requestCancellationManager.createController(routeKey)
}

/**
 * 取消指定路由的所有请求
 * @param routeKey 路由标识
 * @param reason 取消原因
 */
export const cancelRouteRequests = (routeKey: string, reason?: string): void => {
  requestCancellationManager.cancelRequests(routeKey, reason)
}

/**
 * 取消所有请求
 * @param reason 取消原因
 */
export const cancelAllRequests = (reason?: string): void => {
  requestCancellationManager.cancelAllRequests(reason)
}
