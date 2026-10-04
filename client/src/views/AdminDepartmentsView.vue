<!--
  管理端科室管理（TICKET-020，FUNCTIONAL_SPEC 2.5 / SPEC.md 5.4）。
  TICKET-030 改用 element-plus：el-form/el-input 录入，el-table 列科室，el-tag 医生数，
  el-button 操作，el-pagination 翻页。

  分页查看科室、新建、编辑与删除。删除仍有关联医生的科室会被后端以 409 拒绝且
  不落库（FUNCTIONAL_SPEC 5.12 / AC-E-07）；错误经 `@error` 上报提示。名称唯一性
  也由后端保证，前端只做必填提示（FUNCTIONAL_SPEC 5.19）。所有后端调用都经 F-1
  的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const PAGE_SIZE = 10
const items = ref([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const loadError = ref(null)
const formError = ref(null)
const editingId = ref(null)
const loading = ref(false)

const emptyForm = () => ({ name: '', description: '', sort_order: 0 })
const form = ref(emptyForm())

async function load() {
  loading.value = true
  try {
    const data = await props.client.adminDepartments({
      page: page.value,
      page_size: PAGE_SIZE,
      keyword: keyword.value.trim() || undefined,
    })
    items.value = data.items ?? []
    total.value = data.total ?? 0
    loadError.value = null
  } catch (failure) {
    items.value = []
    total.value = 0
    loadError.value = '科室列表加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function goTo(target) {
  if (target < 1 || target === page.value) return
  if ((page.value - 1) * PAGE_SIZE >= total.value && target > page.value) return
  page.value = target
  load()
}

function resetForm() {
  form.value = emptyForm()
  editingId.value = null
  formError.value = null
}

function startEdit(item) {
  editingId.value = item.id
  formError.value = null
  form.value = {
    name: item.name,
    description: item.description ?? '',
    sort_order: item.sort_order ?? 0,
  }
}

function payload() {
  const body = { name: form.value.name.trim(), sort_order: Number(form.value.sort_order) || 0 }
  if (form.value.description.trim()) body.description = form.value.description.trim()
  return body
}

async function submit() {
  if (!form.value.name.trim()) {
    formError.value = '科室名称必填'
    return
  }
  try {
    if (editingId.value === null) await props.client.createDepartment(payload())
    else await props.client.updateDepartment(editingId.value, payload())
    ElMessage.success(editingId.value === null ? '科室已创建' : '科室已更新')
    resetForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function remove(departmentId) {
  try {
    await props.client.deleteDepartment(departmentId)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    ElMessage.success('科室已删除')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-departments">
    <header class="page-head">
      <h1 class="page-head__title">科室管理</h1>
    </header>

    <el-card class="admin-departments__card" shadow="never">
      <template #header>
        <span class="card-title">{{ editingId === null ? '新建科室' : '编辑科室' }}</span>
      </template>

      <el-form
        data-department-form
        :model="form"
        label-width="88px"
        class="admin-departments__form"
        @submit.prevent="submit"
      >
        <el-form-item label="科室名称">
          <el-input v-model="form.name" data-name placeholder="科室名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" data-description placeholder="描述" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input v-model="form.sort_order" data-sort-order type="number" placeholder="排序" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-submit native-type="submit">保存</el-button>
          <el-button v-if="editingId !== null" data-cancel @click="resetForm">取消</el-button>
        </el-form-item>
      </el-form>

      <p
        v-if="formError"
        data-form-error
        class="admin-departments__message admin-departments__message--error"
      >
        {{ formError }}
      </p>
    </el-card>

    <el-card class="admin-departments__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">科室列表</span>
          <el-tag size="small" type="info" effect="plain">{{ total }} 个</el-tag>
        </div>
      </template>

      <el-form data-search class="admin-departments__search" @submit.prevent="search">
        <el-input v-model="keyword" data-keyword placeholder="按名称搜索" clearable />
        <el-button native-type="submit">搜索</el-button>
      </el-form>

      <p v-if="loadError" data-error class="admin-departments__message admin-departments__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="admin-departments__table">
        <template #empty>
          <span data-empty>暂无科室</span>
        </template>
        <el-table-column prop="name" label="名称" min-width="140">
          <template #default="{ row }">
            <span data-cell-name>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180">
          <template #default="{ row }">
            <span data-cell-description>{{ row.description ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" min-width="80">
          <template #default="{ row }">
            <span data-cell-sort>{{ row.sort_order }}</span>
          </template>
        </el-table-column>
        <el-table-column label="医生数" min-width="90">
          <template #default="{ row }">
            <el-tag data-cell-doctor-count size="small" effect="plain" type="info">
              {{ row.doctor_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="160">
          <template #default="{ row }">
            <el-button size="small" :data-edit="row.id" @click="startEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain :data-delete="row.id" @click="remove(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-departments__pager">
        <el-pagination
          data-pagination
          background
          layout="prev, pager, next"
          :current-page="page"
          :page-size="PAGE_SIZE"
          :total="total"
          @current-change="goTo"
        />
      </div>
    </el-card>
  </section>
</template>

<style scoped>
.admin-departments {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 0;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.admin-departments__form {
  max-width: 560px;
}

.admin-departments__search {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.admin-departments__search :deep(.el-input) {
  max-width: 320px;
}

.admin-departments__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.admin-departments__message--error {
  color: var(--el-color-danger);
}

.admin-departments__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
