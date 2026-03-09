import { useState, useCallback, useRef } from 'react'
import { useAiraStore } from '../store/useAiraStore'
import { useWebSocket } from './useWebSocket'
import { useVoiceStream } from './useVoiceStream'

export function useAiraSession() {
  const {
    status, setStatus, setSessionId, addMessage,
    setCurrentGoal, setError, setLastScreenDescription,
  } = useAiraStore()

  const audioContextRef = useRef<AudioContext | null>(null)
  const audioQueueRef = useRef<ArrayBuffer[]>([])
  const isPlayingRef = useRef(false)
  const isSessionReadyRef = useRef(false)
  const nextStartTimeRef = useRef(0)
  const screenStreamRef = useRef<MediaStream | null>(null)
  const [isScreenSharing, setIsScreenSharing] = useState(false)

  const getAudioContext = useCallback(() => {
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 })
      nextStartTimeRef.current = 0
    }
    return audioContextRef.current
  }, [])

  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return
    isPlayingRef.current = true
    setStatus('speaking')

    try {
      const ctx = getAudioContext()
      if (ctx.state === 'suspended') await ctx.resume()

      const scheduleAll = () => {
        while (audioQueueRef.current.length > 0) {
          const buffer = audioQueueRef.current.shift()!
          try {
            const int16 = new Int16Array(buffer)
            const float32 = new Float32Array(int16.length)
            for (let i = 0; i < int16.length; i++) {
              float32[i] = int16[i] / 32768.0
            }
            const audioBuffer = ctx.createBuffer(1, float32.length, 24000)
            audioBuffer.copyToChannel(float32, 0)
            const source = ctx.createBufferSource()
            source.buffer = audioBuffer
            source.connect(ctx.destination)
            const startTime = Math.max(ctx.currentTime + 0.01, nextStartTimeRef.current)
            source.start(startTime)
            nextStartTimeRef.current = startTime + audioBuffer.duration
          } catch {
            // skip bad chunk
          }
        }
      }

      scheduleAll()

      while (nextStartTimeRef.current > ctx.currentTime) {
        await new Promise(resolve => setTimeout(resolve, 50))
        if (audioQueueRef.current.length > 0) scheduleAll()
      }

      setStatus('listening')
    } catch (e) {
      console.error('Audio playback error:', e)
    } finally {
      isPlayingRef.current = false
    }
  }, [getAudioContext, setStatus])

  const handleMessage = useCallback((message: Record<string, unknown>) => {
    const type = message.type as string

    if (type === 'session_started') {
      isSessionReadyRef.current = true
      setSessionId(message.session_id as string)
      setStatus('listening')
      addMessage('aira', message.message as string)
    }
    else if (type === 'transcript') {
      const role = message.role as 'user' | 'aira'
      const text = message.text as string
      if (text?.trim()) addMessage(role, text)
    }
    else if (type === 'audio') {
      const base64 = message.data as string
      const binary = atob(base64)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
      audioQueueRef.current.push(bytes.buffer)
      setStatus('speaking')
      playNextAudio()
    }
    else if (type === 'turn_complete') {
      if (audioQueueRef.current.length === 0 && !isPlayingRef.current) {
        setStatus('listening')
      }
    }
    else if (type === 'goal_plan') {
      setCurrentGoal(message.plan as never)
    }
    else if (type === 'screen_analyzed') {
      setLastScreenDescription(message.description as string)
    }
    else if (type === 'error') {
      setError(message.message as string)
      setStatus('error')
      isSessionReadyRef.current = false
    }
    else if (type === 'session_ended') {
      setStatus('idle')
      setSessionId(null)
      isSessionReadyRef.current = false
      audioContextRef.current?.close()
      audioContextRef.current = null
    }
  }, [setSessionId, setStatus, addMessage, setCurrentGoal,
      setLastScreenDescription, setError, playNextAudio])

  const { connect, disconnect, send, isConnected } = useWebSocket(handleMessage)

  const sendAudioChunk = useCallback((base64: string) => {
    if (isConnected() && isSessionReadyRef.current) {
      send({ type: 'audio', data: base64 })
    }
  }, [send, isConnected])

  const handleSpeechEnd = useCallback(() => {
    if (isSessionReadyRef.current) {
      setStatus('thinking')
    }
  }, [setStatus])

  const { isRecording, startRecording, stopRecording } = useVoiceStream(
    sendAudioChunk,
    handleSpeechEnd,
  )

  const startSession = useCallback(async () => {
    try {
      isSessionReadyRef.current = false
      setStatus('connecting')
      connect()

      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Connection timeout')), 10000)
        const interval = setInterval(() => {
          if (isConnected()) {
            clearInterval(interval)
            clearTimeout(timeout)
            resolve()
          }
        }, 100)
      })

      await startRecording()
    } catch (error) {
      setError((error as Error).message)
      setStatus('error')
    }
  }, [connect, startRecording, setStatus, setError, isConnected])

  const endSession = useCallback(() => {
    isSessionReadyRef.current = false
    stopRecording()
    disconnect()
    setStatus('idle')
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach(t => t.stop())
      screenStreamRef.current = null
      setIsScreenSharing(false)
    }
    audioContextRef.current?.close()
    audioContextRef.current = null
    audioQueueRef.current = []
    isPlayingRef.current = false
  }, [stopRecording, disconnect, setStatus])

  const sendText = useCallback((text: string) => {
    if (isConnected()) {
      send({ type: 'text', data: text })
      addMessage('user', text)
      setStatus('thinking')
    }
  }, [send, isConnected, addMessage, setStatus])

  // ── sendMessage ───────────────────────────────────────────────────────
  // Sends any raw JSON object through the WebSocket.
  // Used by the interruption toggle in Home.tsx:
  //   sendMessage({ type: 'set_interruptions', enabled: false })
  const sendMessage = useCallback((payload: Record<string, unknown>) => {
    if (isConnected()) {
      send(payload)
    }
  }, [send, isConnected])

  const sendScreenshot = useCallback(async () => {
    // Toggle OFF — stop sharing
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach(t => t.stop())
      screenStreamRef.current = null
      setIsScreenSharing(false)
      return
    }

    // Toggle ON — start sharing
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
      screenStreamRef.current = stream
      setIsScreenSharing(true)

      stream.getVideoTracks()[0].onended = () => {
        screenStreamRef.current = null
        setIsScreenSharing(false)
      }

      const track = stream.getVideoTracks()[0]
      let base64: string

      if ('ImageCapture' in window) {
        const imageCapture = new (window as any).ImageCapture(track)
        const bitmap = await imageCapture.grabFrame()
        const canvas = document.createElement('canvas')
        canvas.width = bitmap.width
        canvas.height = bitmap.height
        canvas.getContext('2d')!.drawImage(bitmap, 0, 0)
        base64 = canvas.toDataURL('image/png').split(',')[1]
      } else {
        const video = document.createElement('video')
        video.srcObject = stream
        await new Promise<void>((resolve) => {
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

      if (isConnected() && isSessionReadyRef.current) {
        send({ type: 'screen_context', data: base64, is_image: true })
      }

      try {
        const { api } = await import('../services/api')
        const response = await api.post('/vision/describe', {
          image_base64: base64,
          query: null,
        })
        setLastScreenDescription(response.data.description)
        setError(null)
        addMessage('aira', `I can see your screen: ${response.data.description.slice(0, 120)}...`)
      } catch {
        // Vision API optional
      }

    } catch (err: any) {
      screenStreamRef.current = null
      setIsScreenSharing(false)
      if (err?.name === 'NotAllowedError' || err?.name === 'AbortError') {
        // User cancelled — no error needed
      } else if (err?.name === 'NotSupportedError') {
        setError('Screen sharing is not supported in this browser.')
      } else {
        setError(`Screen capture failed: ${err?.message || 'Unknown error'}`)
      }
    }
  }, [send, isConnected, setError, setLastScreenDescription, addMessage])

  return {
    status,
    isRecording,
    isScreenSharing,
    startSession,
    endSession,
    sendText,
    sendScreenshot,
    sendMessage,   // ← newly exported — used by Home.tsx toggle
    isConnected,
  }
}