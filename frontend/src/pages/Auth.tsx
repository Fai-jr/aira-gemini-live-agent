import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../services/api'
import { useAiraStore } from '../store/useAiraStore'

export default function Auth() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const { setToken, setUser } = useAiraStore()
  const navigate = useNavigate()

  const handleSubmit = async () => {
    setError('')
    setLoading(true)
    try {
      let response
      if (mode === 'register') {
        response = await authApi.register({ email, full_name: fullName, password })
      } else {
        response = await authApi.login({ email, password })
      }
      const data = response.data
      setToken(data.access_token)
      setUser({ id: data.user_id, email: data.email, full_name: data.full_name, preferred_voice: 'aira-default', language: 'en' })
      navigate('/')
    } catch (err: unknown) {
      setError((err as any).response?.data?.detail || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    width: '100%',
    padding: '12px 16px',
    background: 'var(--aira-bg-secondary)',
    border: '1px solid var(--aira-border)',
    borderRadius: 'var(--radius-md)',
    color: 'var(--aira-text-primary)',
    fontSize: '14px',
    transition: 'var(--transition)',
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      background: 'radial-gradient(ellipse at 50% 0%, rgba(108,99,255,0.15) 0%, var(--aira-bg-primary) 70%)',
    }}>
      <div className="glass" style={{
        width: '100%',
        maxWidth: '420px',
        borderRadius: 'var(--radius-xl)',
        padding: '40px',
        animation: 'fadeInUp 0.5s ease',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-cyan))',
            margin: '0 auto 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '28px',
            boxShadow: 'var(--shadow-glow)',
          }}>
            A
          </div>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: '28px',
            fontWeight: 700,
            marginBottom: '6px',
          }} className="gradient-text">
            AIRA
          </h1>
          <p style={{ color: 'var(--aira-text-secondary)', fontSize: '14px' }}>
            AI Real-time Agent
          </p>
        </div>

        {/* Tab toggle */}
        <div style={{
          display: 'flex',
          background: 'var(--aira-bg-secondary)',
          borderRadius: 'var(--radius-md)',
          padding: '4px',
          marginBottom: '24px',
        }}>
          {(['login', 'register'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              style={{
                flex: 1,
                padding: '8px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '14px',
                fontWeight: 500,
                transition: 'var(--transition)',
                background: mode === m ? 'var(--aira-accent-primary)' : 'transparent',
                color: mode === m ? 'white' : 'var(--aira-text-secondary)',
              }}
            >
              {m === 'login' ? 'Sign In' : 'Sign Up'}
            </button>
          ))}
        </div>

        {/* Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {mode === 'register' && (
            <input
              style={inputStyle}
              placeholder="Full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          )}
          <input
            style={inputStyle}
            type="email"
            placeholder="Email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            style={inputStyle}
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          />

          {error && (
            <div style={{
              color: '#ef4444',
              fontSize: '13px',
              padding: '10px 14px',
              background: 'rgba(239,68,68,0.1)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(239,68,68,0.2)',
            }}>
              {error}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            style={{
              padding: '13px',
              borderRadius: 'var(--radius-md)',
              background: loading
                ? 'var(--aira-bg-elevated)'
                : 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-blue))',
              color: 'white',
              fontSize: '15px',
              fontWeight: 600,
              transition: 'var(--transition)',
              opacity: loading ? 0.7 : 1,
              marginTop: '4px',
            }}
          >
            {loading ? 'Please wait...' : mode === 'login' ? 'Sign In to AIRA' : 'Create Account'}
          </button>
        </div>
      </div>
    </div>
  )
}