import axios from 'axios'

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('aira_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('aira_token')
      localStorage.removeItem('aira_user')
      window.location.href = '/auth'
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  register: (data: { email: string; full_name: string; password: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  getMe: () => api.get('/auth/me'),
  updateProfile: (data: Partial<{ full_name: string; preferred_voice: string }>) =>
    api.patch('/auth/me', data),
}

export const memoryApi = {
  list: (params?: { memory_type?: string; pinned_only?: boolean }) =>
    api.get('/memory/', { params }),
  create: (data: { memory_type: string; content: string; key?: string }) =>
    api.post('/memory/', data),
  update: (id: string, data: Partial<{ content: string; is_pinned: boolean }>) =>
    api.patch(`/memory/${id}`, data),
  delete: (id: string) => api.delete(`/memory/${id}`),
}

export const sessionApi = {
  list: () => api.get('/sessions/'),
  get: (id: string) => api.get(`/sessions/${id}`),
  create: (data: { session_type: string }) => api.post('/sessions/', data),
}

export const WS_BASE_URL = ''
