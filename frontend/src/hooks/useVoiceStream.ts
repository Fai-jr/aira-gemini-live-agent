import { useRef, useCallback, useState } from 'react'

const SAMPLE_RATE = 16000
const SILENCE_THRESHOLD = 0.01      // RMS below this = silence
const SILENCE_DURATION_MS = 800    // ms of silence before turn_complete fires
const MIN_SPEECH_MS = 300           // ignore bursts shorter than this

const WORKLET_CODE = `
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = []
    this._bufferSize = 1024
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true
    const channelData = input[0]

    // Calculate RMS for silence detection
    let sum = 0
    for (let i = 0; i < channelData.length; i++) sum += channelData[i] * channelData[i]
    const rms = Math.sqrt(sum / channelData.length)

    for (let i = 0; i < channelData.length; i++) {
      this._buffer.push(channelData[i])
    }

    while (this._buffer.length >= this._bufferSize) {
      const chunk = this._buffer.splice(0, this._bufferSize)
      const pcm16 = new Int16Array(chunk.length)
      for (let i = 0; i < chunk.length; i++) {
        const clamped = Math.max(-1, Math.min(1, chunk[i]))
        pcm16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767
      }
      this.port.postMessage({ pcm16, rms })
    }
    return true
  }
}
registerProcessor('pcm-processor', PCMProcessor)
`

export function useVoiceStream(
  onAudioChunk: (base64: string) => void,
  onSpeechEnd: () => void,
) {
  const [isRecording, setIsRecording] = useState(false)
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const workletNodeRef = useRef<AudioWorkletNode | null>(null)
  const workletUrlRef = useRef<string | null>(null)

  // VAD state
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isSpeakingRef = useRef(false)
  const speechStartRef = useRef(0)

  const resetSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
    silenceTimerRef.current = setTimeout(() => {
      // Only fire turn_complete if user spoke for at least MIN_SPEECH_MS
      const speechDuration = Date.now() - speechStartRef.current
      if (isSpeakingRef.current && speechDuration >= MIN_SPEECH_MS) {
        isSpeakingRef.current = false
        onSpeechEnd()
      }
    }, SILENCE_DURATION_MS)
  }, [onSpeechEnd])

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      streamRef.current = stream

      const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE })
      audioContextRef.current = audioContext

      const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' })
      const workletUrl = URL.createObjectURL(blob)
      workletUrlRef.current = workletUrl

      await audioContext.audioWorklet.addModule(workletUrl)

      const source = audioContext.createMediaStreamSource(stream)
      const workletNode = new AudioWorkletNode(audioContext, 'pcm-processor')
      workletNodeRef.current = workletNode

      workletNode.port.onmessage = (event) => {
        const { pcm16, rms } = event.data

        // Send audio chunk to backend
        const bytes = new Uint8Array(pcm16.buffer)
        let binary = ''
        bytes.forEach((b) => (binary += String.fromCharCode(b)))
        onAudioChunk(btoa(binary))

        // VAD logic
        if (rms > SILENCE_THRESHOLD) {
          if (!isSpeakingRef.current) {
            isSpeakingRef.current = true
            speechStartRef.current = Date.now()
          }
          resetSilenceTimer()
        }
      }

      source.connect(workletNode)
      workletNode.connect(audioContext.destination)
      setIsRecording(true)

    } catch (error) {
      console.error('Microphone access error:', error)
      throw new Error('Could not access microphone. Please allow microphone permission.')
    }
  }, [onAudioChunk, resetSilenceTimer])

  const stopRecording = useCallback(() => {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
    isSpeakingRef.current = false

    workletNodeRef.current?.disconnect()
    workletNodeRef.current = null

    audioContextRef.current?.close()
    audioContextRef.current = null

    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null

    if (workletUrlRef.current) {
      URL.revokeObjectURL(workletUrlRef.current)
      workletUrlRef.current = null
    }

    setIsRecording(false)
  }, [])

  return { isRecording, startRecording, stopRecording }
}
