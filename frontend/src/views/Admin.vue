<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types'

const authStore = useAuthStore()

const activeTab = ref('users')
const users = ref<User[]>([])
const loading = ref(false)

// 获取用户列表
const fetchUsers = async () => {
  loading.value = true
  try {
    const response = await api.get<User[]>('/auth/users')
    users.value = response.data
  } catch (error) {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

// 更新用户角色
const handleUpdateRole = async (userId: string, role: string) => {
  try {
    await api.put(`/auth/users/${userId}/role`, null, {
      params: { role },
    })
    ElMessage.success('更新成功')
    fetchUsers()
  } catch (error) {
    ElMessage.error('更新失败')
  }
}

// 重建索引
const handleRebuildIndex = async () => {
  try {
    const response = await api.post('/search/rebuild-index')
    ElMessage.success(`索引重建完成: 全文 ${response.data.fulltext_indexed} 个，向量 ${response.data.vector_indexed} 个`)
  } catch (error) {
    ElMessage.error('重建索引失败')
  }
}

// 同步所有仓库
const handleSyncAll = async () => {
  try {
    const response = await api.post('/repos/sync-all')
    ElMessage.success(`同步完成: 成功 ${response.data.success.length} 个，失败 ${response.data.failed.length} 个`)
  } catch (error) {
    ElMessage.error('同步失败')
  }
}

// 页面加载
onMounted(() => {
  if (authStore.isAdmin) {
    fetchUsers()
  }
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">系统管理</h1>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="用户管理" name="users">
        <el-table v-loading="loading" :data="users" stripe>
          <el-table-column prop="username" label="用户名" />
          <el-table-column prop="email" label="邮箱" />
          <el-table-column prop="system_role" label="角色" width="120">
            <template #default="{ row }">
              <el-tag :type="row.system_role === 'admin' ? 'danger' : 'info'">
                {{ row.system_role === 'admin' ? '管理员' : '成员' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'danger'">
                {{ row.is_active ? '正常' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180" />
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button
                v-if="row.system_role !== 'admin'"
                type="primary"
                link
                @click="handleUpdateRole(row.id, 'admin')"
              >
                设为管理员
              </el-button>
              <el-button
                v-else-if="row.id !== authStore.user?.id"
                type="warning"
                link
                @click="handleUpdateRole(row.id, 'member')"
              >
                取消管理员
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="系统操作" name="system">
        <el-card>
          <template #header>
            <span>系统维护</span>
          </template>
          <div class="action-list">
            <div class="action-item">
              <div class="action-info">
                <h4>重建搜索索引</h4>
                <p>重新构建全文检索和向量检索索引</p>
              </div>
              <el-button type="primary" @click="handleRebuildIndex">
                执行
              </el-button>
            </div>
            <el-divider />
            <div class="action-item">
              <div class="action-info">
                <h4>同步所有 Git 仓库</h4>
                <p>手动触发所有 Git 仓库的同步操作</p>
              </div>
              <el-button type="primary" @click="handleSyncAll">
                执行
              </el-button>
            </div>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped lang="scss">
.action-list {
  .action-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 0;

    .action-info {
      h4 {
        margin: 0 0 5px;
        font-size: 15px;
        color: #303133;
      }

      p {
        margin: 0;
        color: #909399;
        font-size: 13px;
      }
    }
  }
}
</style>
