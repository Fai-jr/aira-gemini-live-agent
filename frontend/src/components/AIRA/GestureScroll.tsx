/**
 * AIRA Gesture Scroll — v3
 * Hand HIGH in camera frame → scroll up
 * Hand LOW  in camera frame → scroll down
 * Hand MIDDLE → idle (dead zone)
 * Scrolls via backend xdotool — works on Chrome, YouTube, any window.
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision'
import { useAiraStore } from '../../store/useAiraStore'

export function GestureScroll() {
  const { token } = useAiraStore()

  // Single video + canvas — always in DOM, just hidden when panel closed
  const videoRef      = useRef<HTMLVideoElement>(null)
  const canvasRef     = useRef<HTMLCanvasElement>(null)
  const landmarkerRef = useRef<HandLandmarker | null>(null)
  const animRef       = useRef<number>(0)
  const wsRef         = useRef<WebSocket | null>(null)
  const lastSendRef   = useRef<number>(0)
  const activeRef     = useRef(false)  // ref copy so detect() always sees latest

  const [active, setActive]       = useState(false)
  const [loading, setLoading]     = useState(false)
  const [direction, setDirection] = useState<'up' | 'down' | null>(null)
  const [error, setError]         = useState('')
  const [showPanel, setShowPanel] = useState(false)
  const [wsReady, setWsReady]     = useState(false)

  // ── WebSocket ──────────────────────────────────────────────────────────
  const connectWs = useCallback(() => {
    if (!token) return
    const ws = new WebSocket(`ws://localhost:8000/api/v1/gesture-scroll/ws?token=${token}`)
    ws.onopen    = () => { setWsReady(true) }
    ws.onclose   = () => { setWsReady(false); if (activeRef.current) setTimeout(connectWs, 1500) }
    ws.onerror   = () => setError('Backend WebSocket error')
    wsRef.current = ws
  }, [token])

  const sendScroll = useCallback((dir: 'up' | 'down', speed: number) => {
    const now = Date.now()
    if (now - lastSendRef.current < 80) return
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'scroll', direction: dir, speed }))
      lastSendRef.current = now
    }
  }, [])

  // ── MediaPipe init ─────────────────────────────────────────────────────
  const initMediaPipe = useCallback(async (): Promise<boolean> => {
    setLoading(true)
    setError('')
    try {
      const vision = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm'
      )
      landmarkerRef.current = await HandLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath:
            'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
          delegate: 'GPU',
        },
        runningMode: 'VIDEO',
        numHands: 1,
      })
      setLoading(false)
      return true
    } catch (e) {
      setError('Could not load hand model')
      setLoading(false)
      return false
    }
  }, [])

  // ── Detection loop ─────────────────────────────────────────────────────
  const detect = useCallback(() => {
    if (!activeRef.current) return

    const video      = videoRef.current
    const canvas     = canvasRef.current
    const landmarker = landmarkerRef.current

    if (!video || !canvas || !landmarker) {
      animRef.current = requestAnimationFrame(detect)
      return
    }

    if (video.readyState >= 2) {
      const result = landmarker.detectForVideo(video, performance.now())
      const ctx = canvas.getContext('2d')!
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      if (result.landmarks.length > 0) {
        const lm    = result.landmarks[0]
        const wrist = lm[0]
        const y     = wrist.y

        // Draw skeleton
        const CONNECTIONS = [
          [0,1],[1,2],[2,3],[3,4],
          [0,5],[5,6],[6,7],[7,8],
          [5,9],[9,10],[10,11],[11,12],
          [9,13],[13,14],[14,15],[15,16],
          [13,17],[0,17],[17,18],[18,19],[19,20],
        ]
        ctx.strokeStyle = 'rgba(139,92,246,0.9)'
        ctx.lineWidth   = 2
        CONNECTIONS.forEach(([a, b]) => {
          ctx.beginPath()
          ctx.moveTo(lm[a].x * canvas.width, lm[a].y * canvas.height)
          ctx.lineTo(lm[b].x * canvas.width, lm[b].y * canvas.height)
          ctx.stroke()
        })
        lm.forEach(pt => {
          ctx.beginPath()
          ctx.arc(pt.x * canvas.width, pt.y * canvas.height, 4, 0, Math.PI * 2)
          ctx.fillStyle = '#a78bfa'
          ctx.fill()
        })

        // Scroll logic
        let dir: 'up' | 'down' | null = null
        let speed = 0
        if (y < 0.35) {
          dir   = 'up'
          speed = (0.35 - y) / 0.35
        } else if (y > 0.65) {
          dir   = 'down'
          speed = (y - 0.65) / 0.35
        }

        setDirection(dir)
        if (dir) sendScroll(dir, speed)

      } else {
        setDirection(null)
      }
    }

    animRef.current = requestAnimationFrame(detect)
  }, [sendScroll])

  // ── Start ──────────────────────────────────────────────────────────────
  const start = useCallback(async () => {
    const ok = await initMediaPipe()
    if (!ok) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240, facingMode: 'user' },
      })
      const video = videoRef.current!
      video.srcObject = stream
      video.onloadedmetadata = () => {
        video.play().then(() => {
          activeRef.current = true
          setActive(true)
          connectWs()
          animRef.current = requestAnimationFrame(detect)
        })
      }
    } catch {
      setError('Camera permission denied')
    }
  }, [initMediaPipe, connectWs, detect])

  // ── Stop ───────────────────────────────────────────────────────────────
  const stop = useCallback(() => {
    activeRef.current = false
    cancelAnimationFrame(animRef.current)
    const video = videoRef.current
    if (video?.srcObject) {
      ;(video.srcObject as MediaStream).getTracks().forEach(t => t.stop())
      video.srcObject = null
    }
    wsRef.current?.close()
    setActive(false)
    setDirection(null)
    setWsReady(false)
  }, [])

  useEffect(() => () => stop(), [stop])

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <>
      {/*
        Video + canvas are ALWAYS in the DOM once active.
        Panel open = visible. Panel closed = hidden but still running.
        This avoids ref conflicts from conditional rendering.
      */}
      <div style={{
        position: 'fixed',
        // When panel is closed, hide off-screen but keep running
        top: showPanel ? 'auto' : '-9999px',
        left: showPanel ? 'auto' : '-9999px',
        bottom: showPanel ? '90px' : 'auto',
        right: showPanel ? '24px' : 'auto',
        width: '250px',
        background: 'var(--aira-bg-elevated, #1a1a2e)',
        border: '1px solid var(--aira-border, rgba(255,255,255,0.1))',
        borderRadius: '16px',
        padding: '14px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
        zIndex: 999,
        display: showPanel ? 'block' : 'none',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>🤚</span>
            <span style={{ fontWeight: 600, fontSize: '13px', color: 'white' }}>Gesture Scroll</span>
            {active && wsReady && (
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#34d399' }} />
            )}
          </div>
          <button
            onClick={active ? stop : start}
            disabled={loading}
            style={{
              padding: '4px 12px', borderRadius: '20px', fontSize: '11px', fontWeight: 600,
              cursor: loading ? 'default' : 'pointer',
              background: active ? 'rgba(239,68,68,0.15)' : 'rgba(108,99,255,0.2)',
              border: active ? '1px solid rgba(239,68,68,0.4)' : '1px solid rgba(108,99,255,0.4)',
              color: active ? '#f87171' : '#a78bfa',
            }}
          >
            {loading ? 'Loading...' : active ? 'Stop' : 'Enable'}
          </button>
        </div>

        {error && <p style={{ color: '#f87171', fontSize: '11px', marginBottom: '8px' }}>⚠ {error}</p>}

        {/* Camera preview — always rendered, shown when active */}
        <div style={{
          position: 'relative', borderRadius: '10px', overflow: 'hidden',
          background: '#000', marginBottom: '10px', aspectRatio: '4/3',
          display: active ? 'block' : 'none',
        }}>
          <video
            ref={videoRef}
            style={{ width: '100%', display: 'block', transform: 'scaleX(-1)' }}
            playsInline muted
          />
          <canvas
            ref={canvasRef}
            width={320} height={240}
            style={{
              position: 'absolute', inset: 0, width: '100%', height: '100%',
              transform: 'scaleX(-1)', pointerEvents: 'none',
            }}
          />
          {/* Zone overlay */}
          <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', display: 'flex', flexDirection: 'column' }}>
            <div style={{
              height: '35%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: direction === 'up' ? 'rgba(52,211,153,0.2)' : 'transparent',
              borderBottom: '1px dashed rgba(52,211,153,0.3)', transition: 'background 0.1s',
            }}>
              <span style={{ fontSize: '10px', color: '#34d399', fontWeight: 700 }}>
                {direction === 'up' ? '↑ SCROLLING UP' : '↑ UP ZONE'}
              </span>
            </div>
            <div style={{
              height: '30%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              borderBottom: '1px dashed rgba(167,139,250,0.2)',
            }}>
              <span style={{ fontSize: '10px', color: 'rgba(167,139,250,0.4)' }}>— IDLE —</span>
            </div>
            <div style={{
              height: '35%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: direction === 'down' ? 'rgba(248,113,113,0.2)' : 'transparent',
              transition: 'background 0.1s',
            }}>
              <span style={{ fontSize: '10px', color: '#f87171', fontWeight: 700 }}>
                {direction === 'down' ? '↓ SCROLLING DOWN' : '↓ DOWN ZONE'}
              </span>
            </div>
          </div>
        </div>

        {/* Instructions when not active */}
        {!active && (
          <div style={{
            background: 'rgba(255,255,255,0.03)', borderRadius: '10px', padding: '10px',
            fontSize: '12px', color: 'rgba(255,255,255,0.4)', lineHeight: 1.7,
          }}>
            <p style={{ fontWeight: 600, color: 'rgba(255,255,255,0.6)', marginBottom: '4px' }}>How to use:</p>
            <p>☝️ Raise hand high → scroll up</p>
            <p>👇 Lower hand down → scroll down</p>
            <p>🤚 Hand in middle → stop</p>
            <p style={{ marginTop: '6px', fontSize: '11px', color: 'rgba(108,99,255,0.5)' }}>
              Works in Chrome, YouTube, any window
            </p>
          </div>
        )}
      </div>

      {/* Floating button */}
      <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 1000 }}>
        <button
          onClick={() => setShowPanel(p => !p)}
          title="Gesture Scroll"
          style={{
            width: '50px', height: '50px', borderRadius: '50%',
            background: active
              ? 'linear-gradient(135deg, #34d399, #059669)'
              : showPanel
              ? 'linear-gradient(135deg, #6c63ff, #3b82f6)'
              : 'var(--aira-bg-elevated, #1e1e3a)',
            border: active ? '2px solid rgba(52,211,153,0.5)' : '2px solid rgba(108,99,255,0.3)',
            boxShadow: active ? '0 0 20px rgba(52,211,153,0.35)' : '0 4px 20px rgba(0,0,0,0.3)',
            cursor: 'pointer', fontSize: '20px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.2s',
          }}
        >
          {direction === 'up' ? '⬆️' : direction === 'down' ? '⬇️' : '🤚'}
        </button>
      </div>
    </>
  )
}