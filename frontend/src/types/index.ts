// 用户类型
export interface User {
  id: string
  username: string
  email: string
  system_role: string
  is_active: boolean
  created_at: string
  last_login_at?: string
}

// Skill 类型
export interface Skill {
  id: string
  name: string
  source_type: 'private' | 'git'
  title?: string
  summary?: string
  tags?: string
  is_locked: boolean
  locked_by?: string
  created_at: string
  updated_at: string
  created_by?: string
}

// Skill 文件类型
export interface SkillFile {
  file_path: string
  file_name: string
  file_size: number
  file_type: string
  is_skill_md: boolean
}

// Skill 详情类型
export interface SkillDetail {
  skill: Skill
  files: SkillFile[]
  skill_md_content?: string
}

// Git 仓库类型
export interface GitRepo {
  id: string
  name: string
  url: string
  branch: string
  last_sync_at?: string
  last_sync_commit?: string
  sync_status: string
  sync_error?: string
  is_active: boolean
  auto_sync: boolean
  created_at: string
  updated_at: string
  created_by?: string
}

// 版本类型
export interface Version {
  id: string
  skill_id: string
  version_number: number
  version_hash: string
  change_summary?: string
  created_at: string
  created_by?: string
}

// 时间线事件类型
export interface TimelineEvent {
  id: string
  event_type: string
  event_data?: Record<string, unknown>
  created_at: string
  created_by?: string
  created_by_name?: string
}

// 收藏类型
export interface Favorite {
  favorite_id: string
  skill_id: string
  skill_name: string
  title?: string
  summary?: string
  source_type: string
  favorited_at: string
}

// 通知类型
export interface Notification {
  id: string
  type: string
  title: string
  content?: string
  is_read: boolean
  resource_type?: string
  resource_id?: string
  created_at: string
  read_at?: string
}

// 搜索结果类型
export interface SearchResult {
  skill_id: string
  name: string
  title: string
  summary: string
  tags: string[]
  score: number
}

// 分页响应类型
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ============================================
// API 响应类型定义
// ============================================

// 通用 API 响应类型
export interface ApiResponse<T> {
  success: boolean
  data?: T
  message?: string
}

// API 错误响应类型
export interface ApiErrorResponse {
  success: false
  error: string
  message?: string
  details?: Record<string, unknown>
}

// 登录响应类型
export interface LoginResponse {
  success: boolean
  message: string
  user?: User
  token?: string
}

// 用户更新响应类型
export interface UserUpdateResponse {
  success: boolean
  message: string
  user?: User
}

// 操作结果响应类型（通用）
export interface OperationResponse {
  success: boolean
  message: string
}

// 锁操作响应类型
export interface LockResponse {
  success: boolean
  message: string
  locked_by?: string
  locked_at?: string
}

// 解锁操作响应类型
export interface UnlockResponse {
  success: boolean
  message: string
}

// 删除操作响应类型
export interface DeleteResponse {
  success: boolean
  message: string
  deleted_id?: string
}

// 创建操作响应类型
export interface CreateResponse<T> {
  success: boolean
  message: string
  data?: T
}

// 同步操作响应类型
export interface SyncResponse {
  success: boolean
  message: string
  synced_count?: number
  error_count?: number
  errors?: string[]
}
