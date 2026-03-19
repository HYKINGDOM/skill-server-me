<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/utils/api'
import type { SkillDetail } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const skillDetail = ref<SkillDetail | null>(null)
const skillMdContent = ref('')

const skillId = route.params.id as string

// 获取 Skill 详情
const fetchSkillDetail = async () => {
  loading.value = true
  try {
    const response = await api.get<SkillDetail>(`/skills/${skillId}`)
    skillDetail.value = response.data
    skillMdContent.value = response.data.skill_md_content || ''
  } catch (error) {
    ElMessage.error('获取详情失败')
    router.back()
  } finally {
    loading.value = false
  }
}

// 保存
const handleSave = async () => {
  saving.value = true
  try {
    await api.put(`/skills/${skillId}`, {
      skill_md_content: skillMdContent.value,
    })
    ElMessage.success('保存成功')
    router.push(`/skills/${skillId}`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// 页面加载
onMounted(() => {
  fetchSkillDetail()
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
        <h1 class="page-title">编辑 Skill</h1>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="saving" @click="handleSave">
          保存
        </el-button>
        <el-button @click="router.back()">取消</el-button>
      </div>
    </div>

    <el-card>
      <el-form label-width="100px">
        <el-form-item label="Skill 名称">
          <el-input :value="skillDetail?.skill.name" disabled />
        </el-form-item>

        <el-form-item label="SKILL.md">
          <el-input
            v-model="skillMdContent"
            type="textarea"
            :rows="25"
            placeholder="请输入 SKILL.md 内容"
          />
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}
</style>
