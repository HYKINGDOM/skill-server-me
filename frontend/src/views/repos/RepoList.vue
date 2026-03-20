<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/utils/api'
import type { GitRepo, PaginatedResponse } from '@/types'

const loading = ref(false)
const repos = ref<GitRepo[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// 同步状态映射
const syncStatusMap = {
  pending: 'info',
  syncing: 'warning',
  success: 'success',
  failed: 'danger'
}

const syncStatusText = {
  pending: '待同步',
  syncing: '同步中',
  success: '成功',
  failed: '失败'
}

// 导入对话框
const importDialogVisible = ref(false)
const importForm = ref({
  name: '',
  url: '',
  branch: 'main',
})

// 获取仓库列表
const fetchRepos = async () => {
  loading.value = true
  try {
    const response = await api.get<PaginatedResponse<GitRepo>>('/repos', {
      params: {
        page: page.value,
        page_size: pageSize.value,
      },
    })
    repos.value = response.data.items
    total.value = response.data.total
  } catch (error) {
    ElMessage.error('获取仓库列表失败')
  } finally {
    loading.value = false
  }
}

// 导入仓库
const handleImport = async () => {
  if (!importForm.value.name || !importForm.value.url) {
    ElMessage.warning('请填写完整信息')
    return
  }

  try {
    await api.post('/repos', importForm.value)
    ElMessage.success('导入成功')
    importDialogVisible.value = false
    importForm.value = { name: '', url: '', branch: 'main' }
    fetchRepos()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

// 同步仓库
const handleSync = async (repoId: string) => {
  try {
    await api.post(`/repos/${repoId}/sync`)
    ElMessage.success('同步成功')
    fetchRepos()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '同步失败')
  }
}

// 删除仓库
const handleDelete = async (repo: GitRepo) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除仓库 "${repo.name}" 吗？关联的 Skills 也会被标记为删除。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await api.delete(`/repos/${repo.id}`)
    ElMessage.success('删除成功')
    fetchRepos()
  } catch {
    // 用户取消
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 分页变化
const handlePageChange = (newPage: number) => {
  page.value = newPage
  fetchRepos()
}

// 页面加载
onMounted(() => {
  fetchRepos()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">Git 仓库管理</h1>
      <el-button type="primary" icon="Plus" @click="importDialogVisible = true">
        导入仓库
      </el-button>
    </div>

    <el-table v-loading="loading" :data="repos" stripe>
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="url" label="URL" min-width="300" />
      <el-table-column prop="branch" label="分支" width="100" />
      <el-table-column prop="sync_status" label="同步状态" width="100">
        <template #default="{ row }">
          <el-tag
            :type="{
              pending: 'info',
              syncing: 'warning',
              success: 'success',
              failed: 'danger',
            }[row.sync_status as keyof typeof syncStatusMap]"
            size="small"
          >
            {{ { pending: '待同步', syncing: '同步中', success: '成功', failed: '失败' }[row.sync_status as keyof typeof syncStatusText] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_sync_at" label="最后同步" width="180">
        <template #default="{ row }">
          {{ formatDate(row.last_sync_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="auto_sync" label="自动同步" width="100">
        <template #default="{ row }">
          <el-tag :type="row.auto_sync ? 'success' : 'info'" size="small">
            {{ row.auto_sync ? '开启' : '关闭' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button type="primary" link @click="handleSync(row.id)">
            同步
          </el-button>
          <el-button type="danger" link @click="handleDelete(row)">
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
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 导入对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      title="导入 Git 仓库"
      width="500px"
    >
      <el-form :model="importForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="importForm.name" placeholder="仓库名称" />
        </el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="importForm.url" placeholder="Git 仓库 URL" />
        </el-form-item>
        <el-form-item label="分支">
          <el-input v-model="importForm.branch" placeholder="默认 main" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
