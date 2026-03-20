<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, uploadFile } from '@/utils/api'

const router = useRouter()

const createMode = ref<'create' | 'upload'>('create')
const loading = ref(false)

// 创建表单
const createForm = ref({
  name: '',
  skill_md_content: '',
})

// 上传相关
const uploadRef = ref()
const uploadFileList = ref<any[]>([])
const uploadName = ref('')

// 创建 Skill
const handleCreate = async () => {
  if (!createForm.value.name) {
    ElMessage.warning('请输入 Skill 名称')
    return
  }

  loading.value = true
  try {
    await api.post('/skills', createForm.value)
    ElMessage.success('创建成功')
    router.push('/skills')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}

// 上传前验证
const beforeUpload = (file: File) => {
  if (!file.name.endsWith('.zip')) {
    ElMessage.error('只支持 ZIP 文件')
    return false
  }
  
  const isLt50M = file.size / 1024 / 1024 < 50
  if (!isLt50M) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }
  
  return true
}

// 上传 Skill
const handleUpload = async () => {
  if (!uploadName.value) {
    ElMessage.warning('请输入 Skill 名称')
    return
  }
  
  if (uploadFileList.value.length === 0) {
    ElMessage.warning('请选择 ZIP 文件')
    return
  }

  loading.value = true
  try {
    await uploadFile(
      '/skills/upload',
      uploadFileList.value[0].raw,
      { name: uploadName.value }
    )
    ElMessage.success('上传成功')
    router.push('/skills')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    loading.value = false
  }
}

// 文件变化
const handleFileChange = (_file: any, fileList: any[]) => {
  uploadFileList.value = fileList.slice(-1) // 只保留最新文件
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">创建 Skill</h1>
    </div>

    <el-radio-group v-model="createMode" class="mode-selector">
      <el-radio-button label="create">页面创建</el-radio-button>
      <el-radio-button label="upload">上传 ZIP</el-radio-button>
    </el-radio-group>

    <!-- 页面创建 -->
    <el-card v-if="createMode === 'create'" class="form-card">
      <el-form
        :model="createForm"
        label-width="100px"
        @submit.prevent="handleCreate"
      >
        <el-form-item label="Skill 名称" required>
          <el-input
            v-model="createForm.name"
            placeholder="只能包含字母、数字、中划线和下划线"
          />
        </el-form-item>

        <el-form-item label="SKILL.md">
          <el-input
            v-model="createForm.skill_md_content"
            type="textarea"
            :rows="20"
            placeholder="请输入 SKILL.md 内容（可选，系统会生成默认模板）"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleCreate">
            创建
          </el-button>
          <el-button @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 上传 ZIP -->
    <el-card v-else class="form-card">
      <el-form label-width="100px">
        <el-form-item label="Skill 名称" required>
          <el-input
            v-model="uploadName"
            placeholder="只能包含字母、数字、中划线和下划线"
          />
        </el-form-item>

        <el-form-item label="ZIP 文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :file-list="uploadFileList"
            :before-upload="beforeUpload"
            :on-change="handleFileChange"
            accept=".zip"
            drag
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽 ZIP 文件到此处，或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                只能上传 ZIP 文件，且文件大小不超过 50MB
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleUpload">
            上传
          </el-button>
          <el-button @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.mode-selector {
  margin-bottom: 20px;
}

.form-card {
  max-width: 900px;
}
</style>
