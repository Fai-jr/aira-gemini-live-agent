import { useEffect, useRef } from 'react'
import type { TranscriptMessage } from '../../store/useAiraStore'

interface AiraTranscriptProps {
  messages: TranscriptMessage[]
}

export function AiraTranscript({ messages }: AiraTranscriptProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--aira-text-muted)',
        fontSize: '14px',
        fontStyle: 'italic',
      }}>
        Your conversation with AIRA will appear here...
      </div>
    )
  }

  return (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
    }}>
      {messages.map((msg) => (
        <div
          key={msg.id}
          className="fade-in"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
          }}
        >
          <div style={{
            maxWidth: '80%',
            padding: '10px 14px',
            borderRadius: msg.role === 'user'
              ? '18px 18px 4px 18px'
              : '18px 18px 18px 4px',
            background: msg.role === 'user'
              ? 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-blue))'
              : 'var(--aira-bg-elevated)',
            border: msg.role === 'aira' ? '1px solid var(--aira-border)' : 'none',
            fontSize: '14px',
            lineHeight: '1.5',
            color: 'var(--aira-text-primary)',
          }}>
            {msg.text}
          </div>
          <div style={{
            fontSize: '11px',
            color: 'var(--aira-text-muted)',
            marginTop: '4px',
            paddingLeft: '4px',
            paddingRight: '4px',
          }}>
            {msg.role === 'aira' ? 'AIRA' : 'You'} •{' '}
            {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}