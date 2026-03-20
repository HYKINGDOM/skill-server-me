import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import Search from '@/views/Search.vue'
import { api } from '@/utils/api'
import { useRoute } from 'vue-router'

// 模拟路由
vi.mock('vue-router', () => ({
  useRoute: vi.fn()
}))

// 模拟 window.open
vi.mock('@/utils/api', () => ({
  api: {
    get: vi.fn()
  }
}))

describe('Search Component', () => {
  let wrapper: any
  let mockRoute: any

  beforeEach(() => {
    // 重置所有模拟
    vi.resetAllMocks()
    // 模拟路由
    mockRoute = {
      query: {}
    }
    ;(useRoute as vi.Mock).mockReturnValue(mockRoute)
    // 模拟 window.open
    delete (window as any).open;
    (window as any).open = vi.fn();
    // 创建 Pinia 实例
    const pinia = createPinia()
    // 挂载组件
    wrapper = mount(Search, {
      global: {
        plugins: [pinia]
      }
    })
  })

  describe('handleSearch', () => {
    it('should search successfully', async () => {
      // 模拟 API 响应
      const mockResults = {
        data: {
          items: [
            {
              skill_id: 1,
              name: 'test-skill',
              title: 'Test Skill',
              summary: 'Test summary',
              tags: ['test', 'skill'],
              score: 0.95
            }
          ],
          total: 1
        }
      }

      // 设置搜索关键词
      wrapper.vm.searchQuery = 'test'
      // 模拟 API 调用
      vi.spyOn(api, 'get').mockResolvedValueOnce(mockResults)

      // 执行搜索
      await wrapper.vm.handleSearch()

      // 验证结果
      expect(wrapper.vm.results).toEqual(mockResults.data.items)
      expect(wrapper.vm.total).toBe(1)
      expect(wrapper.vm.loading).toBe(false)
    })

    it('should handle search error', async () => {
      // 设置搜索关键词
      wrapper.vm.searchQuery = 'test'
      // 模拟 API 错误
      vi.spyOn(api, 'get').mockRejectedValueOnce(new Error('Search failed'))

      // 执行搜索
      await wrapper.vm.handleSearch()

      // 验证状态
      expect(wrapper.vm.loading).toBe(false)
    })

    it('should not search when query is empty', async () => {
      // 设置空搜索关键词
      wrapper.vm.searchQuery = ''

      // 执行搜索
      await wrapper.vm.handleSearch()

      // 验证 API 未被调用
      expect(api.get).not.toHaveBeenCalled()
    })
  })

  describe('handleView', () => {
    it('should open skill detail in new tab', () => {
      // 执行查看
      wrapper.vm.handleView({ skill_id: 1 })

      // 验证 window.open 被调用
      expect(window.open).toHaveBeenCalledWith('/skills/1', '_blank')
    })
  })

  describe('handlePageChange', () => {
    it('should update page', async () => {
      // 执行分页变化
      await wrapper.vm.handlePageChange(2)

      // 验证页面已更新
      expect(wrapper.vm.page).toBe(2)
    })
  })

  describe('route query watcher', () => {
    it('should set searchQuery when route query changes', async () => {
      // 重新挂载组件，传入带有查询参数的路由
      mockRoute.query.q = 'test'
      wrapper = mount(Search, {
        global: {
          plugins: [createPinia()]
        }
      })

      // 验证 searchQuery 已更新
      expect(wrapper.vm.searchQuery).toBe('test')
    })
  })
})
