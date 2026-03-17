<template>
  <div class="documents-page">
    <div class="page-header">
      <h1 class="page-title">票据识别</h1>
      <p class="page-desc">上传票据图片，一键识别表格与关键信息</p>
    </div>

    <el-tabs v-model="activeTab" class="main-tabs">
      <!-- Tab1: 识别 -->
      <el-tab-pane label="识别" name="recognize">
        <el-card class="upload-card" shadow="never">
          <el-row :gutter="24">
            <el-col :xs="24" :md="10">
              <div class="upload-area">
                <el-upload
                  class="upload-demo"
                  drag
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/*"
                  :on-change="onFileChange"
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">将图片拖到此处，或<em>点击上传</em></div>
                </el-upload>
                <div class="upload-hint">单张图片不超过 {{ MAX_FILE_SIZE_MB }}MB</div>
                <el-button
                  type="primary"
                  size="large"
                  :loading="recognizing"
                  :disabled="!currentFile"
                  @click="doRecognize"
                  class="btn-recognize"
                >
                  {{ recognizing ? '识别中…' : '开始识别' }}
                </el-button>
                <div v-if="recognizing || progressText" class="progress-text">
                  {{ progressText || '正在连接…' }}
                </div>
              </div>
              <div v-if="previewUrl" class="preview-img-wrap">
                <img :src="previewUrl" alt="预览" class="preview-img" />
              </div>
            </el-col>
            <el-col :xs="24" :md="14" v-if="!recognizeResult">
              <div class="result-placeholder">
                <p>上传图片并点击「开始识别」后，结果将显示在此处。</p>
              </div>
            </el-col>
          </el-row>

          <!-- 识别结果：全宽展示，表格可横向滚动 -->
          <template v-if="recognizeResult">
            <el-divider content-position="left">识别结果</el-divider>
            <div class="result-full">
              <div v-if="(recognizeResult.structured?.key_values || []).length" class="kv-section">
                <div class="kv-list">
                  <span
                    v-for="(kv, idx) in (recognizeResult.structured.key_values || [])"
                    :key="idx"
                    class="kv-item"
                  >
                    <strong>{{ kv.key }}:</strong> {{ kv.value }}
                  </span>
                </div>
              </div>
              <el-alert
                v-if="hasRemarkHighlight"
                type="warning"
                show-icon
                :closable="false"
                class="handwriting-alert"
                title="备注列有内容"
                description="以下标红为备注列中填写了内容的单元格，可能存在手写/改动，请重点复核。"
              />
              <el-alert
                v-else-if="(recognizeResult.structured?.tables || []).length > 0"
                type="info"
                show-icon
                :closable="false"
                class="handwriting-alert"
                title="备注列暂无填写内容"
                description="当前表格中备注列无识别到的文字，故未做标红。若原图备注列有内容却未标红，请检查表头是否识别为「备注」或重新上传更清晰的图片。"
              />
              <div
                v-for="(tbl, i) in (recognizeResult.structured?.tables || [])"
                :key="i"
                class="table-scroll-wrap"
              >
                <el-table
                  :data="tbl.rows"
                  border
                  stripe
                  size="default"
                  class="result-table"
                >
                  <el-table-column
                    v-for="(h, j) in tbl.headers"
                    :key="j"
                    :prop="String(j)"
                    :label="h"
                    :min-width="h && h.length > 8 ? 140 : 100"
                  >
                    <template #default="{ row, $index }">
                      <span :class="{ 'cell-handwriting': isRemarkCellWithContent(i, $index, j) }">
                        {{ row[j] }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </template>
        </el-card>
      </el-tab-pane>

      <!-- Tab2: 对比 -->
      <el-tab-pane label="对比" name="compare">
        <el-card shadow="hover">
          <p class="tip">使用上方「识别」分别识别发货单与收货单，或在此处用两张图片依次识别，得到两份结构化数据后进行对比。</p>
          <el-row :gutter="16" style="margin-bottom: 16px">
            <el-col :span="12">
              <div class="compare-card">
                <h4>单据 A（发货单）</h4>
                <el-upload
                  drag
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/*"
                  :on-change="(f) => onCompareFileChange(f, 'a')"
                >
                  <span v-if="!docA">上传图片识别（≤{{ MAX_FILE_SIZE_MB }}MB）</span>
                  <span v-else>已解析，可重新上传</span>
                </el-upload>
                <el-button
                  v-if="fileA"
                  type="primary"
                  size="small"
                  :loading="loadingA"
                  @click="recognizeForCompare('a')"
                  style="margin-top: 8px"
                >
                  识别
                </el-button>
                <div v-if="progressA" class="mini-summary progress-inline">{{ progressA }}</div>
                <div v-else-if="docA" class="mini-summary">表格行数: {{ tableRowCount(docA) }}</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="compare-card">
                <h4>单据 B（收货单）</h4>
                <el-upload
                  drag
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/*"
                  :on-change="(f) => onCompareFileChange(f, 'b')"
                >
                  <span v-if="!docB">上传图片识别（≤{{ MAX_FILE_SIZE_MB }}MB）</span>
                  <span v-else>已解析，可重新上传</span>
                </el-upload>
                <el-button
                  v-if="fileB"
                  type="primary"
                  size="small"
                  :loading="loadingB"
                  @click="recognizeForCompare('b')"
                  style="margin-top: 8px"
                >
                  识别
                </el-button>
                <div v-if="progressB" class="mini-summary progress-inline">{{ progressB }}</div>
                <div v-else-if="docB" class="mini-summary">表格行数: {{ tableRowCount(docB) }}</div>
              </div>
            </el-col>
          </el-row>
          <el-button
            type="primary"
            :disabled="!docA || !docB || comparing"
            :loading="comparing"
            @click="doCompare"
          >
            {{ comparing ? '对比中…' : '执行对比' }}
          </el-button>
          <div v-if="compareResult" class="compare-result">
            <h4>对比摘要</h4>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="涉及品名数">{{ compareResult.summary?.total_keys ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="差异条数">{{ compareResult.summary?.diff_count ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="仅 A 有">仅发货单有: {{ compareResult.summary?.only_in_a ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="仅 B 有">仅收货单有: {{ compareResult.summary?.only_in_b ?? '-' }}</el-descriptions-item>
            </el-descriptions>
            <h4 style="margin-top: 16px">差异明细（同一品名下单据 A/B 字段值不一致）</h4>
            <el-table :data="compareResult.diffs" border size="small">
              <el-table-column prop="key" label="品名/键" width="120" />
              <el-table-column prop="field" label="字段" width="80" />
              <el-table-column prop="value_a" label="单据 A 值" />
              <el-table-column prop="value_b" label="单据 B 值" />
              <el-table-column prop="match" label="一致" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.match ? 'success' : 'danger'" size="small">
                    {{ row.match ? '是' : '否' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <template v-if="onlyInA.length || onlyInB.length">
              <h4 style="margin-top: 16px">仅发货单有（收货单无）</h4>
              <el-table :data="onlyInARows" border size="small" style="margin-bottom: 16px">
                <el-table-column v-for="h in onlyInAHeaders" :key="h" :prop="h" :label="h" min-width="80" show-overflow-tooltip />
              </el-table>
              <h4 style="margin-top: 16px">仅收货单有（发货单无）</h4>
              <el-table :data="onlyInBRows" border size="small">
                <el-table-column v-for="h in onlyInBHeaders" :key="h" :prop="h" :label="h" min-width="80" show-overflow-tooltip />
              </el-table>
            </template>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { recognizeStream, compare } from '../api/documents'

const MAX_FILE_SIZE_MB = 20
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

const activeTab = ref('recognize')
const currentFile = ref(null)
const previewUrl = ref('')
const recognizing = ref(false)
const progressText = ref('')
const recognizeResult = ref(null)

function isRemarkColumnHeader(label, colIndex, headers) {
  const s = label != null ? String(label).trim() : ''
  if (s === '备注' || s.includes('备注') || s === '注') return true
  if (headers && colIndex === headers.length - 1 && !/总价|金额|单价|数量|折扣|原价|折后/.test(s)) return true
  return false
}

const hasRemarkHighlight = computed(() => {
  const tables = recognizeResult.value?.structured?.tables || []
  return tables.some(t => {
    const headers = t?.headers || []
    const rows = t?.rows || []
    const remarkColIdx = headers.findIndex((h, idx) => isRemarkColumnHeader(h, idx, headers))
    if (remarkColIdx === -1) return false
    return rows.some(row => {
      const val = row[remarkColIdx]
      return val != null && String(val).trim() !== ''
    })
  })
})

function isRemarkCellWithContent(tableIndex, rowIndex, colIndex) {
  const tbl = recognizeResult.value?.structured?.tables?.[tableIndex]
  const headers = tbl?.headers || []
  const label = headers[colIndex]
  if (!isRemarkColumnHeader(label, colIndex, headers)) return false
  const row = tbl?.rows?.[rowIndex]
  if (!row) return false
  const val = row[colIndex]
  return val != null && String(val).trim() !== ''
}

function onFileChange(file) {
  const f = file?.raw
  if (f && f.size > MAX_FILE_SIZE_BYTES) {
    ElMessage.warning(`图片大小不能超过 ${MAX_FILE_SIZE_MB}MB，当前 ${(f.size / 1024 / 1024).toFixed(1)}MB`)
    currentFile.value = null
    previewUrl.value = ''
    recognizeResult.value = null
    return
  }
  currentFile.value = f || null
  previewUrl.value = f ? URL.createObjectURL(f) : ''
  recognizeResult.value = null
}

async function doRecognize() {
  if (!currentFile.value) return
  recognizing.value = true
  progressText.value = ''
  recognizeResult.value = null
  try {
    const data = await recognizeStream(currentFile.value, (msg) => {
      progressText.value = msg
    })
    recognizeResult.value = data
    progressText.value = ''
    ElMessage.success('识别完成')
  } catch (e) {
    const msg = typeof e === 'string' ? e : (e?.detail || e?.message || (Array.isArray(e?.detail) ? e.detail[0]?.msg : null) || '识别失败')
    ElMessage.error(msg)
    progressText.value = ''
  } finally {
    recognizing.value = false
  }
}

// 对比 Tab
const fileA = ref(null)
const fileB = ref(null)
const docA = ref(null)
const docB = ref(null)
const loadingA = ref(false)
const loadingB = ref(false)
const progressA = ref('')
const progressB = ref('')
const comparing = ref(false)
const compareResult = ref(null)

const onlyInA = computed(() => {
  const matches = compareResult.value?.matches || []
  return matches
    .filter(m => (m.in_a ?? m.inA) && !(m.in_b ?? m.inB))
    .map(m => ({ key: m.key, row: m.row_a ?? m.rowA ?? [], headers: m.headers_a ?? m.headersA ?? [] }))
})
const onlyInB = computed(() => {
  const matches = compareResult.value?.matches || []
  return matches
    .filter(m => (m.in_b ?? m.inB) && !(m.in_a ?? m.inA))
    .map(m => ({ key: m.key, row: m.row_b ?? m.rowB ?? [], headers: m.headers_b ?? m.headersB ?? [] }))
})
const onlyInAHeaders = computed(() => {
  const fromMatch = onlyInA.value[0]?.headers
  if (fromMatch?.length) return fromMatch
  const fromDoc = docA.value?.tables?.[0]?.headers
  if (fromDoc?.length) return fromDoc
  return ['品名/键']
})
const onlyInBHeaders = computed(() => {
  const fromMatch = onlyInB.value[0]?.headers
  if (fromMatch?.length) return fromMatch
  const fromDoc = docB.value?.tables?.[0]?.headers
  if (fromDoc?.length) return fromDoc
  return ['品名/键']
})
const onlyInARows = computed(() => {
  const headers = onlyInAHeaders.value
  if (!headers.length) return onlyInA.value.map(m => ({ '品名/键': m.key }))
  return onlyInA.value.map(m => {
    const row = m.row || []
    const obj = {}
    headers.forEach((h, i) => {
      obj[h] = (headers.length === 1 && h === '品名/键') ? m.key : (row[i] ?? '')
    })
    return obj
  })
})
const onlyInBRows = computed(() => {
  const headers = onlyInBHeaders.value
  if (!headers.length) return onlyInB.value.map(m => ({ '品名/键': m.key }))
  return onlyInB.value.map(m => {
    const row = m.row || []
    const obj = {}
    headers.forEach((h, i) => {
      obj[h] = (headers.length === 1 && h === '品名/键') ? m.key : (row[i] ?? '')
    })
    return obj
  })
})

function onCompareFileChange(file, which) {
  const f = file?.raw
  if (f && f.size > MAX_FILE_SIZE_BYTES) {
    ElMessage.warning(`图片大小不能超过 ${MAX_FILE_SIZE_MB}MB，当前 ${(f.size / 1024 / 1024).toFixed(1)}MB`)
    if (which === 'a') {
      fileA.value = null
      docA.value = null
    } else {
      fileB.value = null
      docB.value = null
    }
    compareResult.value = null
    return
  }
  if (which === 'a') {
    fileA.value = f || null
    if (!f) docA.value = null
  } else {
    fileB.value = f || null
    if (!f) docB.value = null
  }
  compareResult.value = null
}

async function recognizeForCompare(which) {
  const file = which === 'a' ? fileA.value : fileB.value
  if (!file) return
  if (which === 'a') {
    loadingA.value = true
    progressA.value = ''
  } else {
    loadingB.value = true
    progressB.value = ''
  }
  try {
    const data = await recognizeStream(file, (msg) => {
      if (which === 'a') progressA.value = msg
      else progressB.value = msg
    })
    if (which === 'a') {
      docA.value = data.structured
      progressA.value = ''
    } else {
      docB.value = data.structured
      progressB.value = ''
    }
    ElMessage.success('识别完成')
  } catch (e) {
    const msg = typeof e === 'string' ? e : (e?.message || '识别失败')
    ElMessage.error(msg)
    if (which === 'a') progressA.value = ''
    else progressB.value = ''
  } finally {
    if (which === 'a') loadingA.value = false
    else loadingB.value = false
  }
}

function tableRowCount(doc) {
  const tables = doc?.tables
  if (!tables?.length) return 0
  return (tables[0].rows || []).length
}

async function doCompare() {
  if (!docA.value || !docB.value) return
  comparing.value = true
  compareResult.value = null
  try {
    const data = await compare(docA.value, docB.value, {
      match_key: '品名',
      compare_fields: ['数量', '单位'],
    })
    compareResult.value = data
    ElMessage.success('对比完成')
  } catch (e) {
    ElMessage.error(e?.message || '对比失败')
  } finally {
    comparing.value = false
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 24px;
}
.page-title {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1a1a2e;
  letter-spacing: -0.02em;
}
.page-desc {
  margin: 0;
  font-size: 14px;
  color: #64748b;
}
.main-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}
.main-tabs :deep(.el-tabs__item) {
  font-size: 15px;
}
.upload-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}
.upload-area {
  margin-bottom: 16px;
}
.upload-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}
.btn-recognize {
  margin-top: 12px;
  padding: 10px 24px;
}
.preview-img-wrap {
  margin-top: 16px;
}
.preview-img {
  max-width: 100%;
  max-height: 320px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.result-placeholder {
  color: #64748b;
  padding: 48px 24px;
  text-align: center;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
}
.result-placeholder p {
  margin: 0;
}
.result-full {
  margin-top: 8px;
  padding-top: 20px;
  border-top: 1px solid #f1f5f9;
}
.kv-section {
  margin-bottom: 20px;
}
.kv-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  font-size: 14px;
  color: #334155;
}
.kv-item {
  white-space: nowrap;
}
.kv-item strong {
  color: #1e293b;
  margin-right: 4px;
}
.table-scroll-wrap {
  overflow-x: auto;
  margin-bottom: 24px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
}
.handwriting-alert {
  margin: 8px 0 16px 0;
}
.result-table {
  min-width: max-content;
}
.result-table :deep(.el-table__header th) {
  background: #f8fafc;
  color: #475569;
  font-weight: 600;
  font-size: 13px;
}
.result-table :deep(.el-table__row:hover td) {
  background: #f1f5f9 !important;
}
.cell-handwriting {
  color: #b91c1c;
  font-weight: 700;
  background: rgba(220, 38, 38, 0.08);
  padding: 2px 6px;
  border-radius: 6px;
}
.compare-result h4 {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}
.tip {
  color: #606266;
  margin-bottom: 16px;
  font-size: 13px;
}
.compare-card {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background: #fafafa;
}
.compare-card h4 {
  margin-bottom: 8px;
  font-size: 14px;
}
.mini-summary {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}
.progress-text,
.progress-inline {
  margin-top: 8px;
  font-size: 13px;
  color: #409EFF;
}
.compare-result {
  margin-top: 20px;
}
</style>
