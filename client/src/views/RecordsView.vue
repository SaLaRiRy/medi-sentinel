<!--
  患者侧健康档案（TICKET-018，FUNCTIONAL_SPEC 2.7）。

  只读展示本人档案：档案类型、诊断、治疗方案、处方、就诊日期与建档医生。患者端
  没有写入口（建档/修改/删除只对医生开放，SPEC.md 5.4）。所有后端调用都经 F-1
  的 `client`，本组件不认识传输层；列表加载失败呈现空态并上报（AC-F-12）。
-->
<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const items = ref([])
const loadError = ref(null)

async function load() {
  try {
    items.value = await props.client.myRecords()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '健康档案加载失败'
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="records">
    <p v-if="loadError" data-error class="records__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="records__empty">
      暂无健康档案
    </p>

    <table v-else class="records__table">
      <thead>
        <tr>
          <th>档案类型</th>
          <th>诊断</th>
          <th>治疗方案</th>
          <th>处方</th>
          <th>就诊日期</th>
          <th>医生</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-record-row>
          <td data-cell-type>{{ item.record_type ?? '-' }}</td>
          <td data-cell-diagnosis>{{ item.diagnosis ?? '-' }}</td>
          <td data-cell-treatment>{{ item.treatment ?? '-' }}</td>
          <td data-cell-prescription>{{ item.prescription ?? '-' }}</td>
          <td data-cell-date>{{ item.visit_date ?? '-' }}</td>
          <td data-cell-doctor>{{ item.doctor_name ?? '-' }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
