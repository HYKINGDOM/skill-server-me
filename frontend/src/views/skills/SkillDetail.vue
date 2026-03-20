<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { api, downloadFile } from '@/utils/api'
import type { SkillDetail, SkillFile, Version, TimelineEvent } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const skillDetail = ref<SkillDetail | null>(null)
const activeTab = ref('content')
const selectedFile = ref<SkillFile | null>(null)
const fileContent = ref('')
const versions = ref<Version[]>([])
const timeline = ref<TimelineEvent[]>([])

const skillId = computed(() => route.params.id as string)

// 是否为私有 Skill
const isPrivate = computed(() => skillDetail.value?.skill.source_type === 'private')

// 获取 Skill 详情
const fetchSkillDetail = async () => {
  loading.value = true
  try {
    const response = await api.get<SkillDetail>(`/skills/${skillId.value}`)
    skillDetail.value = response.data
    
    // 如果有 SKILL.md 内容，默认显示
    if (response.data.skill_md_content) {
      fileContent.value = response.data.skill_md_content
    }
    
    // 查找 SKILL.md 文件
    const skillMd = response.data.files.find(f => f.is_skill_md)
    if (skillMd) {
      selectedFile.value = skillMd
    }
  } catch (error) {
    ElMessage.error('获取详情失败')
    router.back()
  } finally {
    loading.value = false
  }
}

// 获取版本列表
const fetchVersions = async () => {
  try {
    const response = await api.get(`/versions/skill/${skillId.value}`)
    versions.value = response.data.items
  } catch (error) {
    console.error('获取版本失败', error)
  }
}

// 获取时间线
const fetchTimeline = async () => {
  try {
    const response = await api.get(`/timeline/skill/${skillId.value}`)
    timeline.value = response.data.items
  } catch (error) {
    console.error('获取时间线失败', error)
  }
}

// 选择文件
const handleFileSelect = async (file: SkillFile) => {
  selectedFile.value = file
  
  try {
    const response = await api.get(`/skills/${skillId.value}/files/${file.file_path}`, {
      responseType: 'text',
    })
    fileContent.value = response.data
  } catch (error) {
    ElMessage.error('获取文件内容失败')
  }
}

// 渲染 Markdown
const renderedContent = computed(() => {
  if (selectedFile.value?.file_name.toUpperCase() === 'SKILL.MD') {
    return marked(fileContent.value)
  }
  return null
})

// 编辑 Skill
const handleEdit = () => {
  router.push(`/skills/${skillId.value}/edit`)
}

// 下载 Skill
const handleDownload = async () => {
  try {
    await downloadFile(
      `/skills/${skillId.value}/download`,
      `${skillDetail.value?.skill.name}.zip`
    )
    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

// 页面加载
onMounted(() => {
  fetchSkillDetail()
  fetchVersions()
  fetchTimeline()
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <el-button link @click="router.back()">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h1 class="page-title">{{ skillDetail?.skill.title || skillDetail?.skill.name }}</h1>
        <el-tag :type="isPrivate ? 'primary' : 'success'" size="small">
          {{ isPrivate ? '私有' : 'Git' }}
        </el-tag>
      </div>
      <div class="header-actions">
        <el-button type="primary" icon="Download" @click="handleDownload">
          下载
        </el-button>
        <el-button
          v-if="isPrivate"
          type="primary"
          icon="Edit"
          @click="handleEdit"
        >
          编辑
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" v-if="skillDetail">
      <!-- 左侧文件树 -->
      <el-col :span="6">
        <el-card class="file-tree-card">
          <template #header>
            <span>文件列表</span>
          </template>
          <div class="file-tree">
            <div
              v-for="file in skillDetail.files"
              :key="file.file_path"
              class="file-item"
              :class="{ active: selectedFile?.file_path === file.file_path }"
              @click="handleFileSelect(file)"
            >
              <el-icon class="file-icon">
                <component :is="file.is_skill_md ? 'Document' : 'Document'" />
              </el-icon>
              <span class="file-name">{{ file.file_name }}</span>
              <span class="file-size">{{ formatFileSize(file.file_size) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧内容区 -->
      <el-col :span="18">
        <el-card>
          <el-tabs v-model="activeTab">
            <el-tab-pane label="内容" name="content">
              <!-- Markdown 预览 -->
              <div
                v-if="renderedContent"
                class="markdown-preview"
                v-html="renderedContent"
              />
              <!-- 代码文件 -->
              <pre v-else class="code-preview">{{ fileContent }}</pre>
            </el-tab-pane>

            <el-tab-pane label="版本历史" name="versions">
              <el-table :data="versions" stripe>
                <el-table-column prop="version_number" label="版本" width="80">
                  <template #default="{ row }">
                    v{{ row.version_number }}
                  </template>
                </el-table-column>
                <el-table-column prop="change_summary" label="变更说明" />
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ formatDate(row.created_at) }}
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="时间线" name="timeline">
              <el-timeline>
                <el-timeline-item
                  v-for="event in timeline"
                  :key="event.id"
                  :timestamp="formatDate(event.created_at)"
                  placement="top"
                >
                  <el-card>
                    <h4>{{ event.event_type }}</h4>
                    <p v-if="event.created_by_name">操作人: {{ event.created_by_name }}</p>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
            </el-tab-pane>

            <el-tab-pane label="元数据" name="metadata">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="名称">
                  {{ skillDetail.skill.name }}
                </el-descriptions-item>
                <el-descriptions-item label="标题">
                  {{ skillDetail.skill.title }}
                </el-descriptions-item>
                <el-descriptions-item label="来源类型">
                  {{ skillDetail.skill.source_type }}
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">
                  {{ formatDate(skillDetail.skill.created_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="更新时间">
                  {{ formatDate(skillDetail.skill.updated_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="skillDetail.skill.is_locked ? 'warning' : 'success'">
                    {{ skillDetail.skill.is_locked ? '编辑中' : '可用' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="摘要" :span="2">
                  {{ skillDetail.skill.summary || '无' }}
                </el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.file-tree-card {
  height: calc(100vh - 200px);
  overflow: auto;
}

.file-tree {
  .file-item {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    cursor: pointer;
    border-radius: 4px;
    transition: background-color 0.2s;

    &:hover {
      background-color: #f5f7fa;
    }

    &.active {
      background-color: #ecf5ff;
      color: #409eff;
    }

    .file-icon {
      margin-right: 8px;
    }

    .file-name {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .file-size {
      color: #909399;
      font-size: 12px;
    }
  }
}

.code-preview {
  background-color: #282c34;
  color: #abb2bf;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
