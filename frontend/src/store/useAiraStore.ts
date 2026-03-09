import { create } from 'zustand'

export type AiraStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'error'

export interface TranscriptMessage {
  id: string
  role: 'user' | 'aira'
  text: string
  timestamp: Date
}

export interface GoalStep {
  step: number
  action: string
  type: string
  details: string
  status: 'pending' | 'active' | 'completed' | 'failed'
}

export interface GoalPlan {
  goal_summary: string
  requires_confirmation: boolean
  steps: GoalStep[]
}

export interface User {
  id: string
  email: string
  full_name: string
  preferred_voice: string
  language: string
}

interface AiraStore {
  // Auth
  token: string | null
  user: User | null
  setToken: (token: string | null) => void
  setUser: (user: User | null) => void
  logout: () => void

  // Session
  sessionId: string | null
  status: AiraStatus
  setSessionId: (id: string | null) => void
  setStatus: (status: AiraStatus) => void

  // Transcript
  transcript: TranscriptMessage[]
  addMessage: (role: 'user' | 'aira', text: string) => void
  clearTranscript: () => void

  // Goal planning
  currentGoal: GoalPlan | null
  setCurrentGoal: (plan: GoalPlan | null) => void
  updateGoalStep: (stepIndex: number, status: GoalStep['status']) => void

  // Screen context
  lastScreenDescription: string | null
  setLastScreenDescription: (desc: string | null) => void

  // UI state
  isSidebarOpen: boolean
  isScreenSharing: boolean
  toggleSidebar: () => void
  setScreenSharing: (val: boolean) => void

  // Errors
  error: string | null
  setError: (error: string | null) => void
}

export const useAiraStore = create<AiraStore>((set, get) => ({
  // Auth
  token: localStorage.getItem('aira_token'),
  user: (() => {
    const stored = localStorage.getItem('aira_user')
    return stored ? JSON.parse(stored) : null
  })(),
  setToken: (token) => {
    if (token) localStorage.setItem('aira_token', token)
    else localStorage.removeItem('aira_token')
    set({ token })
  },
  setUser: (user) => {
    if (user) localStorage.setItem('aira_user', JSON.stringify(user))
    else localStorage.removeItem('aira_user')
    set({ user })
  },
  logout: () => {
  localStorage.removeItem('aira_token')
  localStorage.removeItem('aira_user')
  set({
    token: null,
    user: null,
    sessionId: null,
    status: 'idle',
    transcript: [],
    currentGoal: null,
    lastScreenDescription: null,
    error: null,
  })
},

  // Session
  sessionId: null,
  status: 'idle',
  setSessionId: (id) => set({ sessionId: id }),
  setStatus: (status) => set({ status }),

  // Transcript
  transcript: [],
  addMessage: (role, text) => {
    const message: TranscriptMessage = {
      id: `${Date.now()}-${Math.random()}`,
      role,
      text,
      timestamp: new Date(),
    }
    set((state) => ({ transcript: [...state.transcript, message] }))
  },
  clearTranscript: () => set({ transcript: [] }),

  // Goal planning
  currentGoal: null,
  setCurrentGoal: (plan) => set({ currentGoal: plan }),
  updateGoalStep: (stepIndex, status) => {
    const goal = get().currentGoal
    if (!goal) return
    const steps = [...goal.steps]
    steps[stepIndex] = { ...steps[stepIndex], status }
    set({ currentGoal: { ...goal, steps } })
  },

  // Screen
  lastScreenDescription: null,
  setLastScreenDescription: (desc) => set({ lastScreenDescription: desc }),

  // UI
  isSidebarOpen: false,
  isScreenSharing: false,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  setScreenSharing: (val) => set({ isScreenSharing: val }),

  // Errors
  error: null,
  setError: (error) => set({ error }),
}))