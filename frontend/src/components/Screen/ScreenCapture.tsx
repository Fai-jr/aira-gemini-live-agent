import { useState } from 'react'
import { api } from '../../services/api'
import { useAiraStore } from '../../store/useAiraStore'

export function ScreenCapture() {
  const { addMessage, setLastScreenDescription } = useAiraStore()
  const [isCapturing, setIsCapturing] = useState(false)
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const capture = async (): Promise<string | null> => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
      const track = stream.getVideoTracks()[0]
      let base64: string

      if ('ImageCapture' in window) {
        const ic = new (window as any).ImageCapture(track)
        const bitmap = await ic.grabFrame()
        const canvas = document.createElement('canvas')
        canvas.width = bitmap.width
        canvas.height = bitmap.height
        canvas.getContext('2d')!.drawImage(bitmap, 0, 0)
        base64 = canvas.toDataURL('image/png').split(',')[1]
      } else {
        const video = document.createElement('video')
        video.srcObject = stream
        await new Promise<void>(resolve => {
          video.onloadedmetadata = () => { video.play(); resolve() }
        })
        await new Promise(r => setTimeout(r, 300))
        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        canvas.getContext('2d')!.drawImage(video, 0, 0)
        base64 = canvas.toDataURL('image/png').split(',')[1]
        video.pause()
      }

      track.stop()
      stream.getTracks().forEach(t => t.stop())
      return base64
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        setError('Screen capture failed. Please try again.')
      }
      return null
    }
  }

  const handleDescribe = async () => {
    setIsCapturing(true)
    setError(null)
    setResult(null)
    try {
      const base64 = await capture()
      if (!base64) return

      const [descRes, appRes, actionsRes] = await Promise.all([
        api.post('/vision/describe', { image_base64: base64, query: query || null }),
        api.post('/vision/app-info', { image_base64: base64 }),
        api.post('/vision/suggest-actions', { image_base64: base64 }),
      ])

      const fullResult = {
        description: descRes.data.description,
        app: appRes.data,
        actions: actionsRes.data.actions,
      }

      setResult(fullResult)
      setLastScreenDescription(fullResult.description)
      addMessage('aira', `I can see your screen. ${fullResult.description.slice(0, 100)}...`)
    } catch (e) {
      setError('Analysis failed. Make sure you are logged in.')
    } finally {
      setIsCapturing(false)
    }
  }

  const handleAsk = async () => {
    if (!query.trim()) return
    setIsCapturing(true)
    setError(null)
    try {
      const base64 = await capture()
      if (!base64) return
      const res = await api.post('/vision/describe', { image_base64: base64, query })
      setResult({ description: res.data.description, app: null, actions: [] })
      setLastScreenDescription(res.data.description)
      addMessage('aira', res.data.description)
    } catch {
      setError('Analysis failed.')
    } finally {
      setIsCapturing(false)
    }
  }

  const card = {
    background: 'var(--aira-bg-card)',
    border: '1px solid var(--aira-border)',
    borderRadius: 'var(--radius-lg)',
    padding: '16px',
  }

  const btn = (primary = false) => ({
    padding: '9px 14px',
    borderRadius: 'var(--radius-md)',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
    width: '100%',
    border: primary ? 'none' : '1px solid var(--aira-border)',
    background: primary
      ? 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-blue))'
      : 'var(--aira-bg-elevated)',
    color: primary ? 'white' : 'var(--aira-text-secondary)',
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>

      {/* Full analysis */}
      <div style={card}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--aira-text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '12px' }}>
          Screen Actions
        </div>
        <button onClick={handleDescribe} disabled={isCapturing} style={btn(true)}>
          {isCapturing ? 'Analyzing...' : '🖥️ Analyze My Screen'}
        </button>
      </div>

      {/* Ask a specific question */}
      <div style={card}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--aira-text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '12px' }}>
          Ask About Screen
        </div>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAsk()}
          placeholder="What do you want to know?"
          style={{
            width: '100%', padding: '9px 12px', marginBottom: '8px',
            background: 'var(--aira-bg-secondary)', border: '1px solid var(--aira-border)',
            borderRadius: 'var(--radius-md)', color: 'var(--aira-text-primary)',
            fontSize: '13px', boxSizing: 'border-box', outline: 'none',
          }}
        />
        <button onClick={handleAsk} disabled={isCapturing || !query.trim()} style={btn()}>
          {isCapturing ? 'Capturing...' : '📸 Capture & Ask'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '10px 14px', borderRadius: 'var(--radius-md)',
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          color: '#ef4444', fontSize: '12px',
        }}>
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div style={card}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--aira-accent-primary)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '10px' }}>
            What AIRA Sees
          </div>

          {result.app && (
            <div style={{ fontSize: '11px', color: 'var(--aira-text-muted)', marginBottom: '8px' }}>
              {result.app.app_name} — {result.app.page_title}
            </div>
          )}

          <p style={{ fontSize: '13px', color: 'var(--aira-text-secondary)', lineHeight: '1.6', marginBottom: result.actions?.length ? '12px' : '0' }}>
            {result.description}
          </p>

          {result.actions?.length > 0 && (
            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--aira-text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>
                Suggested Actions
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {result.actions.map((a: any, i: number) => (
                  <div key={i} style={{
                    padding: '8px 10px', background: 'var(--aira-bg-secondary)',
                    borderRadius: 'var(--radius-sm)', fontSize: '12px',
                  }}>
                    <div style={{ color: 'var(--aira-text-primary)', fontWeight: 500, marginBottom: '2px' }}>
                      {a.action}
                    </div>
                    <div style={{ color: 'var(--aira-text-muted)' }}>{a.reason}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
