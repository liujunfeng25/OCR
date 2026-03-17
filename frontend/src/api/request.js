import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

request.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err.response?.data || err.message)
)

export default request
