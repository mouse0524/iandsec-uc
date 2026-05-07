<script setup>
import { ref } from 'vue'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '知识搜索' })

const q = ref('')
const type = ref('all')
const loading = ref(false)
const result = ref(null)
const sql = ref('SELECT id, name, type, category FROM sk_skill LIMIT 20')
const sqlResult = ref(null)

async function search() {
  if (!q.value.trim()) return
  loading.value = true
  try {
    const res = await api.skillKnowSearch({ q: q.value, type: type.value, limit: 20 })
    result.value = res.data
  } finally {
    loading.value = false
  }
}

async function runSql() {
  const res = await api.skillKnowSqlSearch({ query: sql.value })
  sqlResult.value = res.data
}
</script>

<template>
  <CommonPage title="知识搜索" show-footer>
    <div class="sk-theme-page">
    <div class="sk-hero">
      <h2 class="sk-hero-title">分层语义搜索台</h2>
      <p class="sk-hero-sub">结合 Markdown 文档分块、Skill 摘要和 ChromaDB 向量索引进行语义检索，支持 SQL 只读核查。</p>
    </div>
    <NSpace vertical size="large">
      <NCard :bordered="false" class="hero-card">
        <h2>Skill-Know 分层检索</h2>
        <p>基于 Markdown chunks、Skill 和 ChromaDB 向量索引进行知识检索；不可用时自动降级文本搜索。</p>
        <NSpace align="center">
          <NInput v-model:value="q" size="large" placeholder="输入自然语言问题，例如：如何配置 OpenAI？" @keyup.enter="search" />
          <NSelect v-model:value="type" style="width: 140px" :options="[{label:'全部',value:'all'},{label:'Skill',value:'skill'},{label:'文档',value:'document'}]" />
          <NButton type="primary" size="large" :loading="loading" @click="search">搜索</NButton>
        </NSpace>
      </NCard>

      <NGrid v-if="result" :cols="2" :x-gap="16">
        <NGi>
          <NCard title="Skill 结果" :bordered="false">
            <NSpace vertical>
              <NCard v-for="item in result.skills" :key="item.id" size="small" class="result-card">
                <NSpace justify="space-between"><b>{{ item.name }}</b><NTag type="success">{{ item.score || 0 }}</NTag></NSpace>
                <p>{{ item.abstract || item.description }}</p>
                <NTag size="small">{{ item.matched_by || 'text' }}</NTag>
              </NCard>
              <NEmpty v-if="!result.skills?.length" description="无 Skill 结果" />
            </NSpace>
          </NCard>
        </NGi>
        <NGi>
          <NCard title="文档结果" :bordered="false">
            <NSpace vertical>
              <NCard v-for="item in result.documents" :key="item.id" size="small" class="result-card">
                <b>{{ item.title }}</b>
                <p>{{ item.abstract || item.description || item.content?.slice(0, 160) }}</p>
                <NTag size="small" type="info">{{ item.file_type }}</NTag>
              </NCard>
              <NEmpty v-if="!result.documents?.length" description="无文档结果" />
            </NSpace>
          </NCard>
        </NGi>
      </NGrid>

      <NCard v-if="result?.chunks?.length" title="Markdown 片段结果" :bordered="false">
        <NSpace vertical>
          <NCard v-for="item in result.chunks" :key="item.chunk_uri" size="small" class="result-card">
            <NSpace justify="space-between"><b>{{ item.title }}</b><NTag type="info">{{ item.score || 0 }}</NTag></NSpace>
            <p v-if="item.heading" class="muted">{{ item.heading }}</p>
            <p>{{ item.abstract || item.content?.slice(0, 220) }}</p>
            <NTag size="small">{{ item.matched_by || 'vector' }}</NTag>
          </NCard>
        </NSpace>
      </NCard>

      <NCard title="SQL 只读搜索" :bordered="false">
        <NSpace vertical>
          <NInput v-model:value="sql" type="textarea" :autosize="{ minRows: 3, maxRows: 8 }" />
          <NButton type="primary" secondary @click="runSql">执行 SELECT</NButton>
          <pre v-if="sqlResult">{{ JSON.stringify(sqlResult, null, 2) }}</pre>
        </NSpace>
      </NCard>
    </NSpace>
    </div>
  </CommonPage>
</template>

<style scoped>
.hero-card { border-radius: 20px; background: #fff; border: 1px solid #e5e7eb; }
.hero-card h2 { margin-top: 0; }
.result-card { border-radius: 14px; }
.muted { color: #64748b; }
pre { white-space: pre-wrap; background: #0f172a; color: #dbeafe; padding: 16px; border-radius: 12px; max-height: 360px; overflow: auto; }
</style>
