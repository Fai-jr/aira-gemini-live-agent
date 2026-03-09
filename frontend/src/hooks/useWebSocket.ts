import { useRef, useCallback, useEffect } from 'react'
import { useAiraStore } from '../store/useAiraStore'

type MessageHandler = (message: Record<string, unknown>) => void

export function useWebSocket(onMessage: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null)
  const { token, setStatus, setSessionId, setError } = useAiraStore()

  const connect = useCallback(() => {
    if (!token) {
      setError('No authentication token found. Please log in again.')
      return
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')

    // Use the proxy path - Vite will forward this to ws://localhost:8000
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/voice/stream?token=${token}`
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected to AIRA backend')
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        onMessage(message)
      } catch {
        console.error('Failed to parse WebSocket message')
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setStatus('error')
      setError('Connection to AIRA lost. Please try again.')
    }

    ws.onclose = (event) => {
      console.log(`WebSocket closed: code=${event.code}`)
      if (event.code !== 1000 && event.code !== 4001) {
        setStatus('idle')
      }
      wsRef.current = null
      setSessionId(null)
    }
  }, [token, setStatus, setSessionId, setError, onMessage])

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket is not open. Cannot send message.')
    }
  }, [])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      send({ type: 'end_session' })
      setTimeout(() => wsRef.current?.close(1000), 300)
    }
  }, [send])

  const isConnected = useCallback(() => {
    return wsRef.current?.readyState === WebSocket.OPEN
  }, [])

  useEffect(() => {
    return () => {
      wsRef.current?.close(1000)
    }
  }, [])

  return { connect, disconnect, send, isConnected }
}
