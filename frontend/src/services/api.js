import axios from 'axios'

export const TOKEN_KEY = 'recoveryai_token'

const api = axios.create({ baseURL: '/api/v1' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response?.status === 401 && !window.location.hash.includes('login')) {
      localStorage.removeItem(TOKEN_KEY)
      window.location.hash = '#/login'
    }
    return Promise.reject(error)
  }
)

export const formatINR = (value, compact = false) => {
  if (value == null || isNaN(value)) return '—'
  if (compact) {
    const abs = Math.abs(value)
    if (abs >= 1e7) return `₹${(value / 1e7).toFixed(2)}Cr`
    if (abs >= 1e5) return `₹${(value / 1e5).toFixed(2)}L`
    if (abs >= 1e3) return `₹${(value / 1e3).toFixed(1)}K`
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value)
}

export const formatPct = (value, decimals = 1) =>
  value == null || isNaN(value) ? '—' : `${(value * 100).toFixed(decimals)}%`

export default api
