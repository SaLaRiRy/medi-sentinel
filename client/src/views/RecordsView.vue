<!--
  患者侧健康档案（TICKET-018，FUNCTIONAL_SPEC 2.7）。TICKET-029 改用 element-plus：
  el-card 外框 + el-table 只读展示。cell 级 data-* 锚点原样保留；行分组改由 ElTable
  的 `.el-table__row` 承担，因为 ElTable 不支持给 <tr> 写自定义属性。

  患者端没有写入口（建档/修改/删除只对医生开放，SPEC.md 5.4）。所有后端调用都经 F-1
  的 `client`，本组件不认识传输层；列表加载失败呈现空态并上报（AC-F-12）。
-->
<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const items = ref([])
const loading = ref(false)
const loadError = ref(null)

async function load() {
  loading.value = true
  try {
    items.value = await props.client.myRecords()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '健康档案加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="records">
    <el-card class="records__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-head__title">健康档案</span>
          <el-tag size="small" type="info" effect="plain">只读</el-tag>
        </div>
      </template>

      <p v-if="loadError" data-error class="records__message records__message--error">
        {{ loadError }}
      </p>
      <el-table
        v-else
        v-loading="loading"
        :data="items"
        stripe
        class="records__table"
      >
        <template #empty>
          <span data-empty>暂无健康档案</span>
        </template>
        <el-table-column prop="record_type" label="档案类型" min-width="110">
          <template #default="{ row }">
            <span data-cell-type>{{ row.record_type ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="diagnosis" label="诊断" min-width="140">
          <template #default="{ row }">
            <span data-cell-diagnosis>{{ row.diagnosis ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="treatment" label="治疗方案" min-width="140">
          <template #default="{ row }">
            <span data-cell-treatment>{{ row.treatment ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="prescription" label="处方" min-width="140">
          <template #default="{ row }">
            <span data-cell-prescription>{{ row.prescription ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="visit_date" label="就诊日期" min-width="120">
          <template #default="{ row }">
            <span data-cell-date>{{ row.visit_date ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="doctor_name" label="医生" min-width="110">
          <template #default="{ row }">
            <span data-cell-doctor>{{ row.doctor_name ?? '-' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.records {
  padding: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-head__title {
  font-size: 16px;
  font-weight: 600;
}

.records__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.records__message--error {
  color: var(--el-color-danger);
}
</style>
