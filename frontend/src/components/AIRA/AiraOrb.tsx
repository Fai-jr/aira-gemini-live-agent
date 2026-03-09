import { useEffect, useRef } from 'react'
import type { AiraStatus } from '../../store/useAiraStore'

interface AiraOrbProps {
  status: AiraStatus
  onClick: () => void
}

export function AiraOrb({ status, onClick }: AiraOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animFrameRef = useRef<number>(0)
  const timeRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const size = 220
    canvas.width = size
    canvas.height = size

    const draw = () => {
      timeRef.current += 0.02
      const t = timeRef.current
      ctx.clearRect(0, 0, size, size)

      const cx = size / 2
      const cy = size / 2

      // Outer glow rings
      const numRings = status === 'listening' ? 3 : status === 'speaking' ? 4 : 2
      for (let i = numRings; i >= 1; i--) {
        const ringRadius = 75 + i * 18 + Math.sin(t * 2 + i) * (status === 'speaking' ? 8 : 3)
        const alpha = status === 'idle' ? 0.04 : 0.08 / i
        ctx.beginPath()
        ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(108, 99, 255, ${alpha})`
        ctx.lineWidth = 1
        ctx.stroke()
      }

      // Main orb gradient
      let color1 = '#6c63ff'
      let color2 = '#3b82f6'
      if (status === 'listening') { color1 = '#8b5cf6'; color2 = '#06b6d4' }
      if (status === 'speaking') { color1 = '#ec4899'; color2 = '#8b5cf6' }
      if (status === 'thinking') { color1 = '#f59e0b'; color2 = '#6c63ff' }
      if (status === 'error') { color1 = '#ef4444'; color2 = '#dc2626' }

      const orbRadius = status === 'speaking'
        ? 65 + Math.sin(t * 8) * 6 + Math.cos(t * 5) * 3
        : status === 'listening'
        ? 65 + Math.sin(t * 3) * 4
        : 65 + Math.sin(t) * 2

      const gradient = ctx.createRadialGradient(cx - 15, cy - 15, 5, cx, cy, orbRadius)
      gradient.addColorStop(0, color1 + 'ff')
      gradient.addColorStop(0.5, color2 + 'cc')
      gradient.addColorStop(1, color1 + '44')

      // Orb glow
      ctx.shadowColor = color1
      ctx.shadowBlur = status === 'speaking' ? 50 : status === 'listening' ? 40 : 25
      ctx.beginPath()
      ctx.arc(cx, cy, orbRadius, 0, Math.PI * 2)
      ctx.fillStyle = gradient
      ctx.fill()
      ctx.shadowBlur = 0

      // Inner highlight
      const hlGradient = ctx.createRadialGradient(cx - 20, cy - 20, 2, cx - 15, cy - 15, 35)
      hlGradient.addColorStop(0, 'rgba(255,255,255,0.25)')
      hlGradient.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.beginPath()
      ctx.arc(cx, cy, orbRadius, 0, Math.PI * 2)
      ctx.fillStyle = hlGradient
      ctx.fill()

      // Wave bars when speaking or listening
      if (status === 'speaking' || status === 'listening') {
        const bars = 5
        const barWidth = 3
        const spacing = 7
        const totalWidth = bars * barWidth + (bars - 1) * spacing
        const startX = cx - totalWidth / 2

        for (let i = 0; i < bars; i++) {
          const barHeight = status === 'speaking'
            ? 8 + Math.abs(Math.sin(t * 6 + i * 1.2)) * 20
            : 6 + Math.abs(Math.sin(t * 3 + i * 0.8)) * 12
          const x = startX + i * (barWidth + spacing)
          const y = cy - barHeight / 2
          ctx.beginPath()
          ctx.roundRect(x, y, barWidth, barHeight, 2)
          ctx.fillStyle = 'rgba(255,255,255,0.9)'
          ctx.fill()
        }
      }

      // Thinking spinner
      if (status === 'thinking') {
        ctx.beginPath()
        ctx.arc(cx, cy, orbRadius - 10, t * 2, t * 2 + Math.PI * 1.5)
        ctx.strokeStyle = 'rgba(255,255,255,0.6)'
        ctx.lineWidth = 3
        ctx.stroke()
      }

      animFrameRef.current = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(animFrameRef.current)
  }, [status])

  const statusLabel: Record<AiraStatus, string> = {
    idle: 'Tap to speak',
    connecting: 'Connecting...',
    connected: 'Connected',
    listening: 'Listening...',
    thinking: 'Thinking...',
    speaking: 'Speaking...',
    error: 'Error — tap to retry',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
      <div
        onClick={onClick}
        style={{
          cursor: 'pointer',
          borderRadius: '50%',
          transition: 'transform 0.2s ease',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.05)')}
        onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
      >
        <canvas ref={canvasRef} style={{ display: 'block' }} />
      </div>
      <div style={{
        fontSize: '13px',
        color: 'var(--aira-text-secondary)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        fontWeight: 500,
      }}>
        {statusLabel[status]}
      </div>
    </div>
  )
}