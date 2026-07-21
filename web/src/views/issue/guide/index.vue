<script setup>
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: '工单使用教程' })

const stages = [
  {
    name: '提交工单',
    owner: '用户 / 渠道',
    desc: '填写项目名称、标题、描述、附件，',
    importantDesc: '默认为新建状态，提交后将状态转为商务审核才会进入下一步，否则流程不会继续流转。',
  },
  { name: '商务审核', owner: '商务', desc: '审核是否在维保期，然后流转到下一节点。' },
  { name: '技术处理', owner: '技术', desc: '定位问题、补充处理记录，需要转需求时调整状态并指派后续角色。' },
  { name: '产品 / 研发 / 测试', owner: '产品、研发、测试', desc: '按当前状态接力处理，所有沟通沉淀在流转记录备注中。' },
  { name: '现场验证', owner: '技术 / 提交者', desc: '验证修复结果；不通过可回退，新建状态只指派给提交者。' },
  { name: '关闭', owner: '提交者 / 处理人', desc: '确认问题处理完成后关闭；关闭和自己新建不发送邮件提醒。' },
]

const roleCards = [
  { role: '提交者', icon: 'material-symbols:person-edit-outline-rounded', points: ['从工单列表查看我提交的问题', '标题框可搜标题、描述、ID、流转备注', '收到邮件后从链接直接进入详情'] },
  { role: '商务', icon: 'material-symbols:support-agent-rounded', points: ['审核是否在维保期', '跟踪保存查询提升日常筛选效率'] },
  { role: '技术', icon: 'material-symbols:engineering-outline-rounded', points: ['处理当前指派给自己的工单', '现场验证时只保留技术和提交者可指派', '附件可在详情页下载和预览'] },
  { role: '产品 / 研发 / 测试', icon: 'material-symbols:hub-outline-rounded', points: ['按状态接收指派邮件', '备注会进入流转记录并支持查询', '用数据展板观察趋势和长期未更新问题'] },
]
</script>

<template>
  <CommonPage title="工单使用教程" :show-header="false" show-footer>
    <div class="issue-guide-page">
      <section class="guide-hero">
        <div>
          <span class="guide-kicker">工单中心工作流</span>
          <h1>一张图看懂从提交到关闭</h1>
          <p>围绕状态、指派人、备注和邮件提醒推进；谁被指派，谁负责下一步。</p>
        </div>
        <div class="guide-rules">
          <strong>关键规则</strong>
          <span>纯数字标题查询优先命中工单 ID</span>
          <span>邮件只通知当前指派人</span>
          <span>关闭、自己新建不发提醒</span>
        </div>
      </section>

      <section class="tips-panel">
        <h2>日常使用顺序</h2>
        <div class="tips-grid">
          <p><b>查找：</b>先用保存查询定位范围，再用标题框输入关键词或 ID。</p>
          <p><b>处理：</b>状态改变时同步确认当前指派人，系统按指派人发送邮件。</p>
          <p><b>沉淀：</b>每次转交写清备注，后续可通过标题框混合查询追溯。</p>
        </div>
      </section>

      <section class="workflow-strip" aria-label="工单流程">
        <article v-for="(stage, index) in stages" :key="stage.name" class="stage-card">
          <div class="stage-index">{{ index + 1 }}</div>
          <div>
            <h2>{{ stage.name }}</h2>
            <small>{{ stage.owner }}</small>
            <p>
              {{ stage.desc }}
              <span v-if="stage.importantDesc" class="stage-important">
                {{ stage.importantDesc }}
              </span>
            </p>
          </div>
        </article>
      </section>

      <section class="guide-grid">
        <article v-for="card in roleCards" :key="card.role" class="role-card">
          <div class="role-title">
            <TheIcon :icon="card.icon" :size="22" />
            <strong>{{ card.role }}</strong>
          </div>
          <ul>
            <li v-for="point in card.points" :key="point">{{ point }}</li>
          </ul>
        </article>
      </section>
    </div>
  </CommonPage>
</template>

<style scoped>
.issue-guide-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  background: #f5f7fb;
  color: #172033;
}

.guide-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  padding: 26px 28px;
  border: 1px solid #c8d3e3;
  border-radius: 8px;
  background: linear-gradient(135deg, #ffffff 0%, #edf4ff 100%);
}

.guide-kicker {
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
}

.guide-hero h1 {
  margin: 10px 0 8px;
  font-size: 30px;
  letter-spacing: 0;
  color: #111827;
}

.guide-hero p,
.stage-card p,
.tips-panel p {
  margin: 0;
  color: #55657a;
  line-height: 1.7;
}

.guide-rules {
  display: grid;
  gap: 8px;
  align-content: center;
  padding: 16px;
  border-left: 4px solid #0f766e;
  border-radius: 0 8px 8px 0;
  background: rgba(255, 255, 255, 0.86);
}

.guide-rules span {
  color: #36465c;
  font-size: 13px;
}

.workflow-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.stage-card,
.role-card {
  border: 1px solid #d8e0ec;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 18px rgba(20, 31, 51, 0.05);
}

.tips-panel {
  border: 1px solid #1f3b57;
  border-radius: 8px;
  background: #1f3b57;
  box-shadow: 0 10px 22px rgba(31, 59, 87, 0.16);
}

.stage-card {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 12px;
  min-height: 150px;
  padding: 16px;
}

.stage-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #1f3b57;
  color: #fff;
  font-weight: 700;
}

.stage-card h2,
.tips-panel h2 {
  margin: 0 0 6px;
  font-size: 16px;
  letter-spacing: 0;
}

.stage-card small {
  display: block;
  margin-bottom: 8px;
  color: #0f766e;
  font-weight: 700;
}

.stage-important {
  display: block;
  margin-top: 8px;
  padding: 9px 10px;
  border: 1px solid #f6c453;
  border-left: 4px solid #d97706;
  border-radius: 6px;
  background: #fff7da;
  color: #7a3b00;
  font-weight: 700;
}

.guide-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.role-card {
  padding: 16px;
}

.role-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: #0f766e;
}

.role-card ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 18px;
  color: #506075;
  line-height: 1.6;
}

.tips-panel {
  padding: 18px;
}

.tips-panel h2,
.tips-panel p {
  color: #f8fafc;
}

.tips-panel b {
  color: #ffd166;
}

.tips-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 1100px) {
  .guide-hero,
  .workflow-strip,
  .guide-grid,
  .tips-grid {
    grid-template-columns: 1fr;
  }
}
</style>
