<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/utils/api'
import type { Skill, PaginatedResponse } from '@/types'

const router = useRouter()

const loading = ref(false)
const skills = ref<Skill[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const sourceType = ref('')

// 获取 Skill 列表
const fetchSkills = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value,
    }
    
    if (sourceType.value) {
      params.source_type = sourceType.value
    }

    const response = await api.get<PaginatedResponse<Skill>>('/skills', { params })
    skills.value = response.data.items
    total.value = response.data.total
  } catch (error) {
    ElMessage.error('获取列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  if (searchKeyword.value) {
    router.push({ path: '/search', query: { q: searchKeyword.value } })
  }
}

// 创建 Skill
const handleCreate = () => {
  router.push('/skills/create')
}

// 查看 Skill 详情
const handleView = (skill: Skill) => {
  router.push(`/skills/${skill.id}`)
}

// 删除 Skill
const handleDelete = async (skill: Skill) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 Skill "${skill.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await api.delete(`/skills/${skill.id}`)
    ElMessage.success('删除成功')
    fetchSkills()
  } catch {
    // 用户取消
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 分页变化
const handlePageChange = (newPage: number) => {
  page.value = newPage
  fetchSkills()
}

// 页面加载
onMounted(() => {
  fetchSkills()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">Skill 列表</h1>
      <div class="header-actions">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索 Skill..."
          prefix-icon="Search"
          clearable
          style="width: 300px; margin-right: 10px"
          @keyup.enter="handleSearch"
        />
        <el-select
          v-model="sourceType"
          placeholder="来源类型"
          clearable
          style="width: 120px; margin-right: 10px"
          @change="fetchSkills"
        >
          <el-option label="私有" value="private" />
          <el-option label="Git" value="git" />
        </el-select>
        <el-button type="primary" icon="Plus" @click="handleCreate">
          创建 Skill
        </el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="skills"
      stripe
      style="width: 100%"
    >
      <el-table-column prop="name" label="名称" min-width="150">
        <template #default="{ row }">
          <el-link type="primary" @click="handleView(row)">
            {{ row.name }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column prop="source_type" label="来源" width="100">
        <template #default="{ row }">
          <el-tag :type="row.source_type === 'private' ? 'primary' : 'success'" size="small">
            {{ row.source_type === 'private' ? '私有' : 'Git' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="is_locked" label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.is_locked" type="warning" size="small">编辑中</el-tag>
          <el-tag v-else type="success" size="small">可用</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="handleView(row)">
            查看
          </el-button>
          <el-button
            v-if="row.source_type === 'private'"
            type="primary"
            link
            @click="router.push(`/skills/${row.id}/edit`)"
          >
            编辑
          </el-button>
          <el-button
            v-if="row.source_type === 'private'"
            type="danger"
            link
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-container">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next, jumper"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.header-actions {
  display: flex;
  align-items: center;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
