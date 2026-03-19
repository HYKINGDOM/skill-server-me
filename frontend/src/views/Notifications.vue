<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/utils/api'
import type { Notification, PaginatedResponse } from '@/types'

const loading = ref(false)
const notifications = ref<Notification[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const unreadOnly = ref(false)

// 获取通知列表
const fetchNotifications = async () => {
  loading.value = true
  try {
    const response = await api.get<PaginatedResponse<Notification>>('/notifications', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        unread_only: unreadOnly.value,
      },
    })
    notifications.value = response.data.items
    total.value = response.data.total
  } catch (error) {
    ElMessage.error('获取通知列表失败')
  } finally {
    loading.value = false
  }
}

// 标记已读
const handleMarkRead = async (notificationId: string) => {
  try {
    await api.post(`/notifications/${notificationId}/read`)
    fetchNotifications()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 全部标记已读
const handleMarkAllRead = async () => {
  try {
    await api.post('/notifications/read-all')
    ElMessage.success('已全部标记为已读')
    fetchNotifications()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 分页变化
const handlePageChange = (newPage: number) => {
  page.value = newPage
  fetchNotifications()
}

// 页面加载
onMounted(() => {
  fetchNotifications()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">通知中心</h1>
      <div class="header-actions">
        <el-checkbox v-model="unreadOnly" @change="fetchNotifications">
          只显示未读
        </el-checkbox>
        <el-button type="primary" @click="handleMarkAllRead">
          全部标记已读
        </el-button>
      </div>
    </div>

    <div class="notification-list" v-loading="loading">
      <el-card
        v-for="notification in notifications"
        :key="notification.id"
        class="notification-card"
        :class="{ unread: !notification.is_read }"
      >
        <div class="notification-header">
          <div class="notification-title">
            <el-icon v-if="!notification.is_read" color="#409eff"><Bell /></el-icon>
            <span>{{ notification.title }}</span>
          </div>
          <div class="notification-time">
            {{ notification.created_at }}
          </div>
        </div>
        <div class="notification-content">
          {{ notification.content }}
        </div>
        <div class="notification-footer">
          <el-tag size="small" type="info">{{ notification.type }}</el-tag>
          <el-button
            v-if="!notification.is_read"
            type="primary"
            link
            @click="handleMarkRead(notification.id)"
          >
            标记已读
          </el-button>
        </div>
      </el-card>

      <el-empty v-if="notifications.length === 0 && !loading" description="暂无通知" />

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
.header-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.notification-card {
  margin-bottom: 15px;
  
  &.unread {
    border-left: 3px solid #409eff;
    background-color: #ecf5ff;
  }

  .notification-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;

    .notification-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
      color: #303133;
    }

    .notification-time {
      color: #909399;
      font-size: 12px;
    }
  }

  .notification-content {
    color: #606266;
    font-size: 14px;
    line-height: 1.6;
    margin-bottom: 10px;
  }

  .notification-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
