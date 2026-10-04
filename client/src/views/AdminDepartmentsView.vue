<!--
  管理端科室管理（TICKET-020，FUNCTIONAL_SPEC 2.5 / SPEC.md 5.4）。

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

const emptyForm = () => ({ name: '', description: '', sort_order: 0 })
const form = ref(emptyForm())

async function load() {
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
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-departments">
    <form data-department-form class="admin-departments__form" @submit.prevent="submit">
      <input v-model="form.name" data-name placeholder="科室名称" />
      <input v-model="form.description" data-description placeholder="描述" />
      <input v-model="form.sort_order" data-sort-order type="number" placeholder="排序" />
      <button type="submit" data-submit>保存</button>
      <button v-if="editingId !== null" type="button" data-cancel @click="resetForm">
        取消
      </button>
    </form>

    <form data-search class="admin-departments__search" @submit.prevent="search">
      <input v-model="keyword" data-keyword placeholder="按名称搜索" />
      <button type="submit">搜索</button>
    </form>

    <p v-if="formError" data-form-error class="admin-departments__error">{{ formError }}</p>
    <p v-if="loadError" data-error class="admin-departments__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="admin-departments__empty">
      暂无科室
    </p>

    <table v-else class="admin-departments__table">
      <thead>
        <tr>
          <th>名称</th>
          <th>描述</th>
          <th>排序</th>
          <th>医生数</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-department-row>
          <td data-cell-name>{{ item.name }}</td>
          <td data-cell-description>{{ item.description ?? '-' }}</td>
          <td data-cell-sort>{{ item.sort_order }}</td>
          <td data-cell-doctor-count>{{ item.doctor_count }}</td>
          <td class="admin-departments__actions">
            <button type="button" :data-edit="item.id" @click="startEdit(item)">编辑</button>
            <button type="button" :data-delete="item.id" @click="remove(item.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="admin-departments__pager">
      <button type="button" data-prev :disabled="page <= 1" @click="goTo(page - 1)">
        上一页
      </button>
      <button
        type="button"
        data-next
        :disabled="page * PAGE_SIZE >= total"
        @click="goTo(page + 1)"
      >
        下一页
      </button>
    </footer>
  </section>
</template>
