<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/utils/api'
import type { Favorite, PaginatedResponse } from '@/types'

const router = useRouter()

const loading = ref(false)
const favorites = ref<Favorite[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// 获取收藏列表
const fetchFavorites = async () => {
  loading.value = true
  try {
    const response = await api.get<PaginatedResponse<Favorite>>('/favorites', {
      params: {
        page: page.value,
        page_size: pageSize.value,
      },
    })
    favorites.value = response.data.items
    total.value = response.data.total
  } catch (error) {
    ElMessage.error('获取收藏列表失败')
  } finally {
    loading.value = false
  }
}

// 取消收藏
const handleRemove = async (skillId: string) => {
  try {
    await api.delete(`/favorites/${skillId}`)
    ElMessage.success('已取消收藏')
    fetchFavorites()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 查看 Skill
const handleView = (skillId: string) => {
  router.push(`/skills/${skillId}`)
}

// 分页变化
const handlePageChange = (newPage: number) => {
  page.value = newPage
  fetchFavorites()
}

// 页面加载
onMounted(() => {
  fetchFavorites()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">我的收藏</h1>
    </div>

    <el-table
      v-loading="loading"
      :data="favorites"
      stripe
    >
      <el-table-column prop="skill_name" label="名称" min-width="200">
        <template #default="{ row }">
          <el-link type="primary" @click="handleView(row.skill_id)">
            {{ row.skill_name }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column prop="summary" label="摘要" min-width="300">
        <template #default="{ row }">
          <span class="summary-text">{{ row.summary }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="source_type" label="来源" width="100">
        <template #default="{ row }">
          <el-tag :type="row.source_type === 'private' ? 'primary' : 'success'" size="small">
            {{ row.source_type === 'private' ? '私有' : 'Git' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="favorited_at" label="收藏时间" width="180" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button type="primary" link @click="handleView(row.skill_id)">
            查看
          </el-button>
          <el-button type="danger" link @click="handleRemove(row.skill_id)">
            取消收藏
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-container">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.summary-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
