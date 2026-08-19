<template>
  <div class="channel-management">
    <div class="header">
      <h2>渠道管理</h2>
      <el-button :icon="Refresh" circle @click="reloadActiveTab" />
    </div>

    <el-tabs v-model="activeTab" class="tabs" @tab-change="onTabChange">
      <!-- ========== Tab 1: 渠道总览 ========== -->
      <el-tab-pane label="渠道总览" name="overview">
        <div class="stat-cards" v-loading="overviewLoading">
          <el-card class="stat-card">
            <div class="stat-value">{{ overview.today_messages }}</div>
            <div class="stat-label">今日总消息</div>
          </el-card>
          <el-card class="stat-card">
            <div class="stat-value">{{ overview.active_channels }}</div>
            <div class="stat-label">活跃渠道</div>
          </el-card>
          <el-card class="stat-card">
            <div class="stat-value">{{ overview.avg_response_time_ms }} ms</div>
            <div class="stat-label">平均响应时间</div>
          </el-card>
          <el-card class="stat-card">
            <div class="stat-value">{{ (overview.transfer_rate * 100).toFixed(1) }}%</div>
            <div class="stat-label">转人工率</div>
          </el-card>
        </div>

        <el-card class="channel-status-card" header="各渠道状态">
          <el-empty v-if="!overview.channels?.length" description="暂无渠道数据" />
          <div v-else class="channel-grid">
            <el-card
              v-for="ch in overview.channels"
              :key="ch.platform"
              class="channel-item"
              shadow="hover"
            >
              <div class="ch-header">
                <span class="ch-name">{{ ch.display_name }}</span>
                <el-tag :type="ch.enabled ? 'success' : 'info'" size="small">
                  {{ ch.enabled ? '已启用' : '已停用' }}
                </el-tag>
              </div>
              <div class="ch-stats">
                <span>平台: {{ ch.platform }}</span>
                <span>今日消息: {{ ch.today_messages }}</span>
                <span>状态: {{ ch.status }}</span>
              </div>
            </el-card>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- ========== Tab 2: 渠道配置 ========== -->
      <el-tab-pane label="渠道配置" name="configs">
        <el-card v-loading="configsLoading">
          <el-table :data="configs" stripe>
            <el-table-column prop="platform" label="平台" width="140" />
            <el-table-column prop="display_name" label="名称" width="140" />
            <el-table-column label="Webhook URL" min-width="280">
              <template #default="{ row }">
                <span class="webhook-url">{{ row.webhook_url || buildWebhookUrl(row.platform) }}</span>
                <el-button
                  size="small"
                  text
                  :icon="CopyDocument"
                  @click="copyWebhookUrl(row.platform)"
                />
              </template>
            </el-table-column>
            <el-table-column label="启用" width="100">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.enabled"
                  @change="(v: any) => onToggle(row.platform, v)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="240" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="onEditConfig(row)">编辑</el-button>
                <el-button size="small" type="primary" plain @click="onTest(row.platform)">
                  测试连接
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-dialog v-model="configDialogVisible" title="编辑渠道配置" width="560px">
          <el-form :model="configForm" label-width="120px">
            <el-form-item label="平台">
              <el-input :model-value="configForm.platform" disabled />
            </el-form-item>
            <el-form-item label="名称">
              <el-input :model-value="configForm.display_name" disabled />
            </el-form-item>
            <el-form-item label="API Token">
              <el-input
                v-model="configForm.api_token"
                type="password"
                show-password
                placeholder="留空则不修改"
              />
            </el-form-item>
            <el-form-item label="Webhook Secret">
              <el-input
                v-model="configForm.webhook_secret"
                type="password"
                show-password
                placeholder="留空则不修改"
              />
            </el-form-item>
            <el-form-item label="App Key">
              <el-input v-model="configForm.app_key" placeholder="留空则不修改" />
            </el-form-item>
            <el-form-item label="API Base">
              <el-input v-model="configForm.api_base" placeholder="如 https://api.sobot.com" />
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="configForm.enabled" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="configForm.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="configDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="configSubmitting" @click="onSubmitConfig">
              保存
            </el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ========== Tab 3: 会话记录 ========== -->
      <el-tab-pane label="会话记录" name="conversations">
        <el-card class="filter-card">
          <el-form inline>
            <el-form-item label="平台">
              <el-select
                v-model="convFilter.platform"
                placeholder="全部平台"
                clearable
                style="width: 160px"
              >
                <el-option
                  v-for="c in platformsForFilter"
                  :key="c.platform"
                  :label="c.display_name"
                  :value="c.platform"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select
                v-model="convFilter.status"
                placeholder="全部状态"
                clearable
                style="width: 140px"
              >
                <el-option label="active" value="active" />
                <el-option label="closed" value="closed" />
                <el-option label="transferred" value="transferred" />
              </el-select>
            </el-form-item>
            <el-form-item label="关键词">
              <el-input
                v-model="convFilter.keyword"
                placeholder="用户名/会话 ID"
                clearable
                style="width: 200px"
                @keyup.enter="loadConversations(1)"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadConversations(1)">查询</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card v-loading="convLoading">
          <el-table :data="conversations" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="platform" label="平台" width="120" />
            <el-table-column prop="external_user_name" label="用户" min-width="120" show-overflow-tooltip />
            <el-table-column prop="external_session_id" label="外部会话 ID" min-width="180" show-overflow-tooltip />
            <el-table-column prop="channel_type" label="类型" width="100" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="convStatusType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="onViewConversation(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination">
            <el-pagination
              v-model:current-page="convFilter.page"
              v-model:page-size="convFilter.page_size"
              :total="convTotal"
              layout="total, prev, pager, next, sizes"
              :page-sizes="[10, 20, 50, 100]"
              @current-change="loadConversations()"
              @size-change="loadConversations(1)"
            />
          </div>
        </el-card>

        <el-drawer v-model="convDrawerVisible" title="会话消息详情" size="50%">
          <div v-loading="convMsgLoading" class="msg-timeline">
            <el-empty v-if="!convMessages.length" description="暂无消息" />
            <el-timeline v-else>
              <el-timeline-item
                v-for="m in convMessages"
                :key="m.id"
                :timestamp="formatTime(m.created_at)"
                :type="m.role === 'user' ? 'primary' : 'success'"
                placement="top"
              >
                <div class="msg-item">
                  <el-tag size="small" :type="m.role === 'user' ? 'primary' : 'success'">
                    {{ m.role }}
                  </el-tag>
                  <div class="msg-content">{{ m.content }}</div>
                  <div v-if="m.intent" class="msg-meta">意图: {{ m.intent }}</div>
                  <div v-if="m.model_used" class="msg-meta">模型: {{ m.model_used }}</div>
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-drawer>
      </el-tab-pane>

      <!-- ========== Tab 4: Webhook 日志 ========== -->
      <el-tab-pane label="Webhook 日志" name="logs">
        <el-card class="filter-card">
          <el-form inline>
            <el-form-item label="平台">
              <el-select
                v-model="logFilter.platform"
                placeholder="全部平台"
                clearable
                style="width: 160px"
              >
                <el-option
                  v-for="c in platformsForFilter"
                  :key="c.platform"
                  :label="c.display_name"
                  :value="c.platform"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select
                v-model="logFilter.status"
                placeholder="全部状态"
                clearable
                style="width: 140px"
              >
                <el-option label="success" value="success" />
                <el-option label="failed" value="failed" />
                <el-option label="ignored" value="ignored" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadLogs(1)">查询</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card v-loading="logLoading">
          <el-table :data="logs" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="platform" label="平台" width="120" />
            <el-table-column prop="message_id" label="消息 ID" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="logStatusType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="error" label="错误" min-width="200" show-overflow-tooltip />
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="onViewLog(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination">
            <el-pagination
              v-model:current-page="logFilter.page"
              v-model:page-size="logFilter.page_size"
              :total="logTotal"
              layout="total, prev, pager, next, sizes"
              :page-sizes="[10, 20, 50, 100]"
              @current-change="loadLogs()"
              @size-change="loadLogs(1)"
            />
          </div>
        </el-card>

        <el-dialog v-model="logDialogVisible" title="日志详情" width="640px">
          <pre class="json-view">{{ logDetailJson }}</pre>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Refresh } from '@element-plus/icons-vue'
import {
  getChannelOverview,
  getChannelConfigs,
  saveChannelConfig,
  toggleChannelStatus,
  testChannelConnection,
  getConversations,
  getConversationMessages,
  getWebhookLogs,
} from '@/api/channel'
import type {
  ChannelConfig,
  ChannelConversation,
  ChannelConversationMessage,
  ChannelOverview,
  WebhookLog,
} from '@/types'

// ----- 通用 -----
const activeTab = ref<'overview' | 'configs' | 'conversations' | 'logs'>('overview')

/** API 基地址（用于拼装 Webhook URL） */
const apiBase = (import.meta.env.VITE_API_BASE_URL || '') + '/api/v1'

/** 拼装 Webhook URL */
function buildWebhookUrl(platform: string): string {
  return `${apiBase}/webhook/${platform}`
}

/** 复制 Webhook URL 到剪贴板 */
async function copyWebhookUrl(platform: string) {
  const url = buildWebhookUrl(platform)
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('Webhook URL 已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制: ' + url)
  }
}

/** 时间格式化 */
function formatTime(ts: string | null | undefined): string {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return ts
  }
}

/** 重新加载当前 Tab */
function reloadActiveTab() {
  onTabChange(activeTab.value)
}

function onTabChange(name: string | number) {
  const tab = String(name)
  if (tab === 'overview') loadOverview()
  else if (tab === 'configs') loadConfigs()
  else if (tab === 'conversations') loadConversations(1)
  else if (tab === 'logs') loadLogs(1)
}

// ----- Tab 1: 渠道总览 -----
const overview = ref<ChannelOverview>({
  today_messages: 0,
  active_channels: 0,
  avg_response_time_ms: 0,
  transfer_rate: 0,
  channels: [],
})
const overviewLoading = ref(false)

async function loadOverview() {
  overviewLoading.value = true
  try {
    const res = await getChannelOverview()
    overview.value = res.data
  } finally {
    overviewLoading.value = false
  }
}

// ----- Tab 2: 渠道配置 -----
const configs = ref<ChannelConfig[]>([])
const configsLoading = ref(false)
const configDialogVisible = ref(false)
const configSubmitting = ref(false)
const configForm = reactive<ChannelConfig>({
  platform: '',
  display_name: '',
  enabled: false,
  api_token: '',
  webhook_secret: '',
  app_key: '',
  api_base: '',
  remark: '',
})

const platformsForFilter = computed(() => configs.value)

async function loadConfigs() {
  configsLoading.value = true
  try {
    const res = await getChannelConfigs()
    configs.value = res.data
  } finally {
    configsLoading.value = false
  }
}

function onEditConfig(row: ChannelConfig) {
  configForm.platform = row.platform
  configForm.display_name = row.display_name
  configForm.enabled = row.enabled
  configForm.api_token = ''
  configForm.webhook_secret = ''
  configForm.app_key = row.app_key || ''
  configForm.api_base = row.api_base || ''
  configForm.remark = row.remark || ''
  configDialogVisible.value = true
}

async function onSubmitConfig() {
  configSubmitting.value = true
  try {
    await saveChannelConfig({ ...configForm })
    ElMessage.success('配置已保存')
    configDialogVisible.value = false
    await loadConfigs()
  } finally {
    configSubmitting.value = false
  }
}

async function onToggle(platform: string, enabled: boolean) {
  await toggleChannelStatus(platform, enabled)
  ElMessage.success(`${platform} 已${enabled ? '启用' : '停用'}`)
  await loadConfigs()
}

async function onTest(platform: string) {
  try {
    const res = await testChannelConnection(platform)
    if (res.data?.success) {
      ElMessage.success(res.data.message || '测试通过')
    } else {
      ElMessage.error(res.data?.message || '测试失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '测试失败')
  }
}

// ----- Tab 3: 会话记录 -----
const conversations = ref<ChannelConversation[]>([])
const convTotal = ref(0)
const convLoading = ref(false)
const convFilter = reactive({
  platform: '',
  status: '',
  keyword: '',
  page: 1,
  page_size: 20,
})
const convDrawerVisible = ref(false)
const convMessages = ref<ChannelConversationMessage[]>([])
const convMsgLoading = ref(false)

async function loadConversations(page?: number) {
  if (page) convFilter.page = page
  convLoading.value = true
  try {
    const res = await getConversations({
      platform: convFilter.platform || undefined,
      status: convFilter.status || undefined,
      keyword: convFilter.keyword || undefined,
      page: convFilter.page,
      page_size: convFilter.page_size,
    })
    const payload = res.data as any
    // 兼容后端 { items, total, page, page_size }；若异常退化空数组避免 .map is not a function
    conversations.value = Array.isArray(payload?.items) ? payload.items : []
    convTotal.value = typeof payload?.total === 'number' ? payload.total : 0
  } catch (e: any) {
    ElMessage.error(e?.message || '会话记录加载失败')
  } finally {
    convLoading.value = false
  }
}

async function onViewConversation(row: ChannelConversation) {
  if (!row?.internal_session_id) {
    ElMessage.warning('该会话暂未关联内部对话，无法查看消息')
    return
  }
  convDrawerVisible.value = true
  convMessages.value = []
  convMsgLoading.value = true
  try {
    const res = await getConversationMessages(row.internal_session_id)
    const data = res.data as any
    // 后端返回数组；若异常退化空数组
    convMessages.value = Array.isArray(data) ? data : []
  } catch (e: any) {
    ElMessage.error(e?.message || '消息详情加载失败')
  } finally {
    convMsgLoading.value = false
  }
}

function convStatusType(status: string) {
  if (status === 'active') return 'success'
  if (status === 'transferred') return 'warning'
  if (status === 'closed') return 'info'
  return ''
}

// ----- Tab 4: Webhook 日志 -----
const logs = ref<WebhookLog[]>([])
const logTotal = ref(0)
const logLoading = ref(false)
const logFilter = reactive({
  platform: '',
  status: '',
  page: 1,
  page_size: 20,
})
const logDialogVisible = ref(false)
const logDetailJson = ref('')

async function loadLogs(page?: number) {
  if (page) logFilter.page = page
  logLoading.value = true
  try {
    const res = await getWebhookLogs({
      platform: logFilter.platform || undefined,
      status: logFilter.status || undefined,
      page: logFilter.page,
      page_size: logFilter.page_size,
    })
    logs.value = res.data.items
    logTotal.value = res.data.total
  } finally {
    logLoading.value = false
  }
}

function onViewLog(row: WebhookLog) {
  try {
    const parsed = row.raw_body ? JSON.parse(row.raw_body) : row
    logDetailJson.value = JSON.stringify(parsed, null, 2)
  } catch {
    logDetailJson.value = row.raw_body || JSON.stringify(row, null, 2)
  }
  logDialogVisible.value = true
}

function logStatusType(status: string) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'ignored') return 'info'
  return ''
}

// ----- 初始化 -----
onMounted(loadOverview)
</script>

<style scoped lang="scss">
.channel-management {
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    h2 {
      margin: 0;
    }
  }
  .tabs {
    background: #fff;
    padding: 16px;
    border-radius: 4px;
  }
  .stat-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 16px;
    .stat-card {
      text-align: center;
      .stat-value {
        font-size: 24px;
        font-weight: 600;
        color: #409eff;
      }
      .stat-label {
        margin-top: 8px;
        color: #909399;
        font-size: 13px;
      }
    }
  }
  .channel-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
    .channel-item {
      .ch-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        .ch-name {
          font-weight: 600;
        }
      }
      .ch-stats {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 13px;
        color: #606266;
      }
    }
  }
  .webhook-url {
    font-family: monospace;
    font-size: 12px;
    color: #606266;
    word-break: break-all;
  }
  .filter-card {
    margin-bottom: 16px;
  }
  .pagination {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
  .msg-timeline {
    padding: 0 12px;
    .msg-item {
      .msg-content {
        margin: 8px 0;
        padding: 8px;
        background: #f5f7fa;
        border-radius: 4px;
        white-space: pre-wrap;
        word-break: break-word;
      }
      .msg-meta {
        font-size: 12px;
        color: #909399;
      }
    }
  }
  .json-view {
    background: #f5f7fa;
    padding: 12px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 12px;
    max-height: 60vh;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }
}
</style>
