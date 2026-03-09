import { useState, useRef } from 'react'
import { useAiraStore } from '../store/useAiraStore'
import { useAiraSession } from '../hooks/useAiraSession'
import { AiraOrb } from '../components/AIRA/AiraOrb'
import { AiraTranscript } from '../components/AIRA/AiraTranscript'
import { AiraGoalPanel } from '../components/AIRA/AiraGoalPanel'
import { MemoryPanel } from '../components/AIRA/MemoryPanel'
import { useNavigate } from 'react-router-dom'
import { ScreenCapture } from '../components/Screen/ScreenCapture'

export default function Home() {
  const { user, transcript, currentGoal, setCurrentGoal, error, logout } = useAiraStore()
  const { status, startSession, endSession, sendText, sendScreenshot, isScreenSharing, sendMessage } = useAiraSession()
  const [textInput, setTextInput] = useState('')
  const [isActive, setIsActive] = useState(false)
  const [showMemory, setShowMemory] = useState(false)

  // ── Interruption toggle state ──────────────────────────────────────────
  // true  = AIRA listens in background and can be interrupted mid-sentence
  // false = AIRA finishes speaking fully before listening again
  const [interruptionsEnabled, setInterruptionsEnabled] = useState(true)

  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  const handleOrbClick = async () => {
    if (status === 'idle' || status === 'error') {
      setIsActive(true)
      await startSession()
    } else {
      setIsActive(false)
      endSession()
    }
  }

  // ── Toggle interruptions and notify backend ────────────────────────────
  const handleToggleInterruptions = () => {
    const newValue = !interruptionsEnabled
    setInterruptionsEnabled(newValue)

    // Tell the backend via WebSocket
    // sendMessage sends any JSON object through the active WS connection
    sendMessage({ type: 'set_interruptions', enabled: newValue })
  }

  const getOrbHint = () => {
    switch (status) {
      case 'idle':       return 'TAP TO SPEAK'
      case 'connecting': return 'CONNECTING...'
      case 'listening':  return 'LISTENING... SPEAK NOW'
      case 'thinking':   return 'AIRA IS THINKING...'
      case 'speaking':   return 'AIRA IS SPEAKING'
      case 'error':      return 'TAP TO RETRY'
      default:           return 'TAP TO SPEAK'
    }
  }

  const handleSendText = () => {
    if (textInput.trim()) {
      sendText(textInput.trim())
      setTextInput('')
    }
  }

  const handleLogout = () => {
    endSession()
    logout()
    navigate('/auth')
  }

  // Grid columns — memory panel takes full right side when open
  const gridColumns = showMemory
    ? '1fr 360px'
    : isActive && currentGoal
    ? '1fr 280px 360px'
    : isActive
    ? '1fr 280px'
    : currentGoal
    ? '1fr 360px'
    : '1fr'

  return (
    <div style={{
      minHeight: '100vh',
      display: 'grid',
      gridTemplateColumns: gridColumns,
      gridTemplateRows: 'auto 1fr',
      gap: '0',
      background: 'radial-gradient(ellipse at 50% -20%, rgba(108,99,255,0.12) 0%, var(--aira-bg-primary) 60%)',
    }}>

      {/* Header */}
      <header className="glass" style={{
        gridColumn: '1 / -1',
        padding: '16px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--aira-border)',
        borderRadius: '0',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-cyan))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: '16px',
            boxShadow: '0 0 20px rgba(108,99,255,0.4)',
          }}>
            A
          </div>
          <div>
            <div style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: '18px',
            }} className="gradient-text">
              AIRA
            </div>
            <div style={{ fontSize: '11px', color: 'var(--aira-text-muted)', marginTop: '-2px' }}>
              AI Real-time Agent
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Status indicator */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: 'var(--radius-full)',
            background: 'var(--aira-bg-elevated)',
            border: '1px solid var(--aira-border)',
            fontSize: '12px',
            color: status === 'listening' || status === 'speaking'
              ? 'var(--aira-accent-primary)'
              : 'var(--aira-text-muted)',
          }}>
            <div style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: status === 'error'
                ? '#ef4444'
                : status === 'idle'
                ? 'var(--aira-text-muted)'
                : 'var(--aira-accent-primary)',
              animation: status === 'listening' || status === 'speaking'
                ? 'blink 1s infinite'
                : 'none',
            }} />
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </div>

          {/* ── Interruption Toggle Switch ─────────────────────────────── */}
          {/* Only shown when a session is active — no point showing it when idle */}
          {isActive && (
            <div
              title={
                interruptionsEnabled
                  ? 'Interruptions ON — you can speak while AIRA is talking'
                  : 'Interruptions OFF — AIRA will finish before listening again'
              }
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--aira-bg-elevated)',
                border: '1px solid var(--aira-border)',
                cursor: 'pointer',
                userSelect: 'none',
              }}
              onClick={handleToggleInterruptions}
            >
              {/* Toggle pill */}
              <div style={{
                width: '36px',
                height: '20px',
                borderRadius: '10px',
                background: interruptionsEnabled
                  ? 'var(--aira-accent-primary)'   // purple = ON
                  : 'var(--aira-bg-surface, #333)', // dark = OFF
                position: 'relative',
                transition: 'background 0.25s ease',
                flexShrink: 0,
                border: '1px solid rgba(255,255,255,0.1)',
              }}>
                {/* Toggle knob */}
                <div style={{
                  position: 'absolute',
                  top: '2px',
                  left: interruptionsEnabled ? '18px' : '2px',
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  background: 'white',
                  transition: 'left 0.25s ease',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                }} />
              </div>

              {/* Label */}
              <span style={{
                fontSize: '12px',
                color: interruptionsEnabled
                  ? 'var(--aira-accent-primary)'
                  : 'var(--aira-text-muted)',
                fontWeight: 500,
                transition: 'color 0.25s ease',
                whiteSpace: 'nowrap',
              }}>
                {interruptionsEnabled ? ' Can interrupt' : ' No interrupt'}
              </span>
            </div>
          )}

          {/* Memory toggle button */}
          <button
            onClick={() => setShowMemory(!showMemory)}
            title="View AIRA's memories"
            style={{
              padding: '8px 14px',
              borderRadius: 'var(--radius-md)',
              background: showMemory ? 'rgba(108,99,255,0.15)' : 'var(--aira-bg-elevated)',
              border: showMemory ? '1px solid rgba(108,99,255,0.4)' : '1px solid var(--aira-border)',
              color: showMemory ? 'var(--aira-accent-primary)' : 'var(--aira-text-secondary)',
              fontSize: '13px',
              cursor: 'pointer',
              transition: 'var(--transition)',
            }}
          >
             Memory
          </button>

          {/* Share Screen toggle button */}
          <button
            onClick={sendScreenshot}
            title={isScreenSharing ? 'Stop sharing screen' : 'Share screen with AIRA'}
            style={{
              padding: '8px 14px',
              borderRadius: 'var(--radius-md)',
              background: isScreenSharing ? 'rgba(239,68,68,0.1)' : 'var(--aira-bg-elevated)',
              border: isScreenSharing ? '1px solid rgba(239,68,68,0.4)' : '1px solid var(--aira-border)',
              color: isScreenSharing ? '#ef4444' : 'var(--aira-text-secondary)',
              fontSize: '13px',
              transition: 'var(--transition)',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!isScreenSharing) {
                e.currentTarget.style.borderColor = 'var(--aira-border-hover)'
                e.currentTarget.style.color = 'var(--aira-text-primary)'
              }
            }}
            onMouseLeave={(e) => {
              if (!isScreenSharing) {
                e.currentTarget.style.borderColor = 'var(--aira-border)'
                e.currentTarget.style.color = 'var(--aira-text-secondary)'
              }
            }}
          >
            {isScreenSharing ? '⏹ Stop Sharing' : '🖥️ Share Screen'}
          </button>

          {/* User menu */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--aira-bg-elevated)',
            border: '1px solid var(--aira-border)',
            fontSize: '13px',
            color: 'var(--aira-text-secondary)',
          }}>
            <div style={{
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-blue))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '11px',
              fontWeight: 700,
              color: 'white',
            }}>
              {user?.full_name?.charAt(0).toUpperCase()}
            </div>
            {user?.full_name?.split(' ')[0]}
            <button
              onClick={handleLogout}
              style={{
                background: 'none',
                color: 'var(--aira-text-muted)',
                fontSize: '12px',
                padding: '2px 6px',
                borderRadius: 'var(--radius-sm)',
                marginLeft: '4px',
                cursor: 'pointer',
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '32px 24px',
        overflow: 'hidden',
        position: 'relative',
      }}>
        {/* Error banner */}
        {error && (
          <div style={{
            width: '100%',
            maxWidth: '600px',
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.3)',
            color: '#ef4444',
            fontSize: '13px',
            marginBottom: '20px',
            animation: 'fadeIn 0.3s ease',
          }}>
            {error}
          </div>
        )}

        {/* AIRA Orb */}
        <div style={{ marginBottom: '12px' }}>
          <AiraOrb status={status} onClick={handleOrbClick} />
        </div>

        {/* Orb hint text */}
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          letterSpacing: '0.12em',
          marginBottom: '28px',
          transition: 'color 0.3s ease',
          color: status === 'listening'
            ? 'var(--aira-accent-primary)'
            : status === 'speaking'
            ? 'var(--aira-accent-cyan)'
            : status === 'thinking'
            ? 'var(--aira-accent-blue)'
            : 'var(--aira-text-muted)',
        }}>
          {getOrbHint()}
        </div>

        {/* Greeting when idle */}
        {!isActive && transcript.length === 0 && (
          <div style={{
            textAlign: 'center',
            animation: 'fadeInUp 0.6s ease',
            marginBottom: '32px',
          }}>
            <h2 style={{
              fontFamily: 'var(--font-display)',
              fontSize: '32px',
              fontWeight: 700,
              marginBottom: '10px',
            }}>
              Hello, {user?.full_name?.split(' ')[0]}.
            </h2>
            <p style={{
              color: 'var(--aira-text-secondary)',
              fontSize: '16px',
              maxWidth: '400px',
            }}>
              Tap the orb to start talking to AIRA. Just speak naturally — she will respond automatically when you stop talking.
            </p>
          </div>
        )}

        {/* Transcript */}
        {transcript.length > 0 && (
          <div className="glass" style={{
            width: '100%',
            maxWidth: '680px',
            borderRadius: 'var(--radius-xl)',
            display: 'flex',
            flexDirection: 'column',
            height: '380px',
            marginBottom: '16px',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '12px 16px',
              borderBottom: '1px solid var(--aira-border)',
              fontSize: '12px',
              color: 'var(--aira-text-muted)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <span>Conversation</span>
              <span>{transcript.length} messages</span>
            </div>
            <AiraTranscript messages={transcript} />
          </div>
        )}

        {/* Text input */}
        {isActive && (
          <div
            className="glass"
            style={{
              width: '100%',
              maxWidth: '680px',
              borderRadius: 'var(--radius-xl)',
              display: 'flex',
              gap: '10px',
              padding: '10px 10px 10px 20px',
              animation: 'fadeInUp 0.3s ease',
            }}
          >
            <input
              ref={inputRef}
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
              placeholder="Or type a message to AIRA..."
              style={{
                flex: 1,
                background: 'none',
                border: 'none',
                color: 'var(--aira-text-primary)',
                fontSize: '14px',
                outline: 'none',
              }}
            />
            <button
              onClick={handleSendText}
              style={{
                padding: '10px 18px',
                borderRadius: 'var(--radius-lg)',
                background: 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-blue))',
                color: 'white',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Send
            </button>
          </div>
        )}
      </main>

      {/* Memory panel sidebar */}
      {showMemory && (
        <aside style={{
          padding: '24px 16px',
          overflowY: 'auto',
          borderLeft: '1px solid var(--aira-border)',
          minWidth: '320px',
          maxWidth: '360px',
          animation: 'slideInRight 0.3s ease',
        }}>
          <MemoryPanel />
        </aside>
      )}

      {/* Vision sidebar */}
      {isActive && !showMemory && (
        <aside style={{
          padding: '24px 16px',
          overflowY: 'auto',
          borderLeft: '1px solid var(--aira-border)',
          minWidth: '280px',
          animation: 'slideInRight 0.3s ease',
        }}>
          <ScreenCapture />
        </aside>
      )}

      {/* Goal panel sidebar */}
      {currentGoal && !showMemory && (
        <aside style={{
          padding: '24px 16px 24px 0',
          overflowY: 'auto',
          animation: 'slideInRight 0.3s ease',
        }}>
          <AiraGoalPanel
            plan={currentGoal}
            onClose={() => setCurrentGoal(null)}
          />
        </aside>
      )}
    </div>
  )
}