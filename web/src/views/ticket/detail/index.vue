<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NAlert } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TicketDetailModal from '@/views/ticket/components/TicketDetailModal.vue'
import api from '@/api'

defineOptions({ name: '工单详情' })

const route = useRoute()
const ticket = ref({})
const loading = ref(false)
const errorMessage = ref('')

async function loadTicket() {
  const ticketId = Number(route.query.ticket_id || 0)
  if (!ticketId) {
    errorMessage.value = '缺少工单ID'
    ticket.value = {}
    return
  }
  loading.value = true
  errorMessage.value = ''
  ticket.value = { id: ticketId }
  try {
    const res = await api.getTicketById({ ticket_id: ticketId })
    ticket.value = res?.data || {}
  } catch {
    errorMessage.value = '加载工单详情失败'
  } finally {
    loading.value = false
  }
}

watch(() => route.query.ticket_id, loadTicket, { immediate: true })
</script>

<template>
  <CommonPage :show-header="false">
    <div class="ticket-detail-page">
      <NAlert v-if="errorMessage" type="error">{{ errorMessage }}</NAlert>
      <TicketDetailModal v-else embedded :visible="true" :ticket="ticket" :loading="loading" />
    </div>
  </CommonPage>
</template>

<style scoped>
.ticket-detail-page {
  min-height: calc(100vh - 150px);
}
</style>
