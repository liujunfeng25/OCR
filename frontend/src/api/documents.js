import request from './request'

// 开发和生产都走相对路径，由 Vite 代理到后端，避免跨域预检导致 405
const API_BASE = '/api'
// 使用短路径 /doc 避免被误解析成 docur/ts（原 /documents）
const DOC_PREFIX = '/doc'

/**
 * 上传票据图片，识别并返回结构化数据与 HTML（普通模式）
 * @param {File} file
 * @returns {Promise<{ structured, html_snippet, image_id }>}
 */
export function recognize(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post(DOC_PREFIX + '/recognize', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 90000,
  })
}

// 流式识别超时（毫秒）
const RECOGNIZE_STREAM_TIMEOUT_MS = 5 * 60 * 1000 // 5 分钟

/**
 * 流式识别：通过 SSE 实时推送进度，最后返回结果
 * @param {File} file
 * @param {function(string): void} onProgress - 进度文案回调，如 "1/3 正在保存文件…"
 * @returns {Promise<{ structured, html_snippet, image_id }>}
 */
export function recognizeStream(file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  const url = API_BASE + DOC_PREFIX + '/recognize?stream=1'
  if (import.meta.env.DEV) console.log('[recognizeStream] POST', url)
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), RECOGNIZE_STREAM_TIMEOUT_MS)
  return new Promise((resolve, reject) => {
    fetch(url, {
      method: 'POST',
      body: form,
      credentials: 'omit',
      signal: controller.signal,
    })
      .then(async (res) => {
        clearTimeout(timeoutId)
        if (import.meta.env.DEV) console.log('[recognizeStream] response', res.status, res.statusText, res.url)
        if (!res.ok) {
          const text = await res.text()
          if (import.meta.env.DEV) console.warn('[recognizeStream] error body', text)
          let err = res.statusText
          try {
            const d = JSON.parse(text)
            err = d.detail || (Array.isArray(d.detail) ? d.detail[0]?.msg : null) || text || err
          } catch {
            if (text && text.length < 500) err = text
          }
          reject(new Error(err))
          return
        }
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let result = null
        function read() {
          reader.read().then(({ done, value }) => {
            if (done) {
              if (result) resolve(result)
              else reject(new Error('未收到识别结果'))
              return
            }
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''
            let event = null
            for (const line of lines) {
              if (line.startsWith('event: ')) event = line.slice(7).trim()
              else if (line.startsWith('data: ') && event) {
                const data = line.slice(6)
                if (event === 'progress' && onProgress) onProgress(data)
                else if (event === 'result') {
                  try {
                    result = JSON.parse(data)
                  } catch (_) {
                    reject(new Error('解析结果失败'))
                  }
                } else if (event === 'error') {
                  reject(new Error(data))
                }
              }
            }
            read()
          }).catch(reject)
        }
        read()
      })
      .catch((err) => {
        clearTimeout(timeoutId)
        if (err.name === 'AbortError') {
          reject(new Error('识别超时（约 5 分钟），请重试。若仍失败可查看后端是否崩溃。'))
        } else if (err.message && err.message.toLowerCase().includes('network')) {
          reject(new Error('连接断开，可能是后端识别时崩溃或超时，请重试并查看后端日志。'))
        } else {
          reject(err)
        }
      })
  })
}

/**
 * 发货单 vs 收货单对比
 * @param {object} docA - 结构化数据 A
 * @param {object} docB - 结构化数据 B
 * @param {object} options - { match_key, compare_fields }
 */
export function compare(docA, docB, options = {}) {
  return request.post(DOC_PREFIX + '/compare', {
    doc_a: docA,
    doc_b: docB,
    rules: {
      match_key: options.match_key || '品名',
      compare_fields: options.compare_fields || ['数量', '单位'],
    },
  })
}
