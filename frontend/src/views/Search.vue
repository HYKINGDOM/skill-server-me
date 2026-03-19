<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/utils/api'
import type { SearchResult, PaginatedResponse } from '@/types'

const route = useRoute()

const loading = ref(false)
const searchQuery = ref('')
const searchMode = ref('hybrid')
const results = ref<SearchResult[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// 搜索
const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  loading.value = true
  try {
    const response = await api.get<PaginatedResponse<SearchResult>>('/search', {
      params: {
        q: searchQuery.value,
        mode: searchMode.value,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    results.value = response.data.items
    total.value = response.data.total
  } catch (error) {
    ElMessage.error('搜索失败')
  } finally {
    loading.value = false
  }
}

// 查看详情
const handleView = (result: SearchResult) => {
  window.open(`/skills/${result.skill_id}`, '_blank')
}

// 分页变化
const handlePageChange = (newPage: number) => {
  page.value = newPage
  handleSearch()
}

// 监听 URL 参数
watch(
  () => route.query.q,
  (newQuery) => {
    if (newQuery) {
      searchQuery.value = newQuery as string
      handleSearch()
    }
  },
  { immediate: true }
)

// 页面加载
onMounted(() => {
  if (route.query.q) {
    searchQuery.value = route.query.q as string
    handleSearch()
  }
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">搜索</h1>
    </div>

    <div class="search-box">
      <el-input
        v-model="searchQuery"
        placeholder="输入关键词搜索 Skill..."
        size="large"
        clearable
        @keyup.enter="handleSearch"
      >
        <template #prepend>
          <el-select v-model="searchMode" style="width: 120px">
            <el-option label="混合检索" value="hybrid" />
            <el-option label="全文检索" value="fulltext" />
            <el-option label="向量检索" value="vector" />
          </el-select>
        </template>
        <template #append>
          <el-button icon="Search" @click="handleSearch">搜索</el-button>
        </template>
      </el-input>
    </div>

    <div class="search-results" v-loading="loading">
      <div v-if="results.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无搜索结果" />
      </div>

      <el-card
        v-for="result in results"
        :key="result.skill_id"
        class="result-card"
        @click="handleView(result)"
      >
        <div class="result-header">
          <h3 class="result-title">{{ result.title || result.name }}</h3>
          <el-tag size="small">相关度: {{ result.score.toFixed(2) }}</el-tag>
        </div>
        <p class="result-summary">{{ result.summary }}</p>
        <div class="result-footer">
          <div class="tag-list">
            <el-tag
              v-for="tag in result.tags"
              :key="tag"
              size="small"
              type="info"
            >
              {{ tag }}
            </el-tag>
          </div>
          <span class="result-name">{{ result.name }}</span>
        </div>
      </el-card>

      <div v-if="total > pageSize" class="pagination-container">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.search-box {
  margin-bottom: 20px;
}

.result-card {
  margin-bottom: 15px;
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;

    .result-title {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      margin: 0;
    }
  }

  .result-summary {
    color: #606266;
    font-size: 14px;
    line-height: 1.6;
    margin-bottom: 10px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .result-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .tag-list {
      display: flex;
      gap: 5px;
    }

    .result-name {
      color: #909399;
      font-size: 12px;
    }
  }
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
