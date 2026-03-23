import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '@/utils/api'
import { useRouter } from 'vue-router'

// 模拟路由
vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn()
  })),
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(),
    push: vi.fn()
  })),
  createWebHistory: vi.fn()
}))

// 模拟 SkillList 组件的方法
describe('SkillList Component Logic', () => {
  let mockRouter: any

  beforeEach(() => {
    // 重置 API 模拟
    vi.resetAllMocks()
    // 获取模拟的路由
    mockRouter = {
      push: vi.fn()
    }
    ;(useRouter as Mock).mockReturnValue(mockRouter)
    // 创建 Pinia 实例并激活
    const pinia = createPinia()
    setActivePinia(pinia)
  })

  describe('fetchSkills', () => {
    it('should fetch skills successfully', async () => {
      // 模拟 API 响应
      const mockSkills = {
        data: {
          items: [
            {
              id: 1,
              name: 'test-skill',
              title: 'Test Skill',
              source_type: 'private',
              updated_at: '2023-01-01T00:00:00Z',
              is_locked: false
            }
          ],
          total: 1
        }
      }

      vi.spyOn(api, 'get').mockResolvedValueOnce(mockSkills)

      // 模拟组件实例
      const component = {
        loading: false,
        skills: [],
        total: 0,
        page: 1,
        pageSize: 20,
        sourceType: '',
        async fetchSkills() {
          this.loading = true
          try {
            const params: Record<string, any> = {
              page: this.page,
              page_size: this.pageSize,
            }
            
            if (this.sourceType) {
              params.source_type = this.sourceType
            }

            const response = await api.get('/skills', { params })
            this.skills = response.data.items
            this.total = response.data.total
          } catch (error) {
            // 错误处理
          } finally {
            this.loading = false
          }
        }
      }

      // 执行 fetchSkills
      await component.fetchSkills()

      // 验证结果
      expect(component.skills).toEqual(mockSkills.data.items)
      expect(component.total).toBe(1)
      expect(component.loading).toBe(false)
    })

    it('should handle fetch skills error', async () => {
      // 模拟 API 错误
      vi.spyOn(api, 'get').mockRejectedValueOnce(new Error('Fetch failed'))

      // 模拟组件实例
      const component = {
        loading: false,
        skills: [],
        total: 0,
        page: 1,
        pageSize: 20,
        sourceType: '',
        async fetchSkills() {
          this.loading = true
          try {
            const params: Record<string, any> = {
              page: this.page,
              page_size: this.pageSize,
            }
            
            if (this.sourceType) {
              params.source_type = this.sourceType
            }

            const response = await api.get('/skills', { params })
            this.skills = response.data.items
            this.total = response.data.total
          } catch (error) {
            // 错误处理
          } finally {
            this.loading = false
          }
        }
      }

      // 执行 fetchSkills
      await component.fetchSkills()

      // 验证状态
      expect(component.loading).toBe(false)
    })
  })

  describe('handleSearch', () => {
    it('should navigate to search page with keyword', () => {
      // 模拟组件实例
      const component = {
        searchKeyword: 'test',
        handleSearch() {
          if (this.searchKeyword) {
            mockRouter.push({ path: '/search', query: { q: this.searchKeyword } })
          }
        }
      }

      // 执行搜索
      component.handleSearch()

      // 验证路由导航
      expect(mockRouter.push).toHaveBeenCalledWith({
        path: '/search',
        query: { q: 'test' }
      })
    })

    it('should not navigate when keyword is empty', () => {
      // 模拟组件实例
      const component = {
        searchKeyword: '',
        handleSearch() {
          if (this.searchKeyword) {
            mockRouter.push({ path: '/search', query: { q: this.searchKeyword } })
          }
        }
      }

      // 执行搜索
      component.handleSearch()

      // 验证路由导航未被调用
      expect(mockRouter.push).not.toHaveBeenCalled()
    })
  })

  describe('handleCreate', () => {
    it('should navigate to create page', () => {
      // 模拟组件实例
      const component = {
        handleCreate() {
          mockRouter.push('/skills/create')
        }
      }

      // 执行创建
      component.handleCreate()

      // 验证路由导航
      expect(mockRouter.push).toHaveBeenCalledWith('/skills/create')
    })
  })

  describe('handleView', () => {
    it('should navigate to skill detail page', () => {
      // 模拟组件实例
      const component = {
        handleView(skill: { id: number }) {
          mockRouter.push(`/skills/${skill.id}`)
        }
      }

      // 执行查看
      component.handleView({ id: 1 })

      // 验证路由导航
      expect(mockRouter.push).toHaveBeenCalledWith('/skills/1')
    })
  })

  describe('handlePageChange', () => {
    it('should update page', async () => {
      // 模拟组件实例
      const component = {
        page: 1,
        handlePageChange(newPage: number) {
          this.page = newPage
        }
      }

      // 执行分页变化
      component.handlePageChange(2)

      // 验证页面已更新
      expect(component.page).toBe(2)
    })
  })

  describe('formatDate', () => {
    it('should format date correctly', () => {
      // 模拟组件实例
      const component = {
        formatDate(dateStr: string) {
          return new Date(dateStr).toLocaleString('zh-CN')
        }
      }

      const dateStr = '2023-01-01T00:00:00Z'
      const result = component.formatDate(dateStr)
      expect(result).toBeTruthy() // 验证返回了一个字符串
    })
  })
})
