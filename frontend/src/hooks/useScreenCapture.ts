import { useState, useRef, useCallback } from 'react'
import { api } from '../services/api'

export interface ScreenAnalysis {
  description: string
  app_name?: string
  actions?: Array<{ action: string; reason: string; type: string }>
}

export function useScreenCapture() {
  const [isCapturing, setIsCapturing] = useState(false)
  const [lastScreenshot, setLastScreenshot] = useState<string | null>(null)
  const [lastAnalysis, setLastAnalysis] = useState<ScreenAnalysis | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const captureScreen = useCallback(async (): Promise<string | null> => {
    try {
      setIsCapturing(true)

      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      })

      streamRef.current = stream
      const track = stream.getVideoTracks()[0]

      // Use ImageCapture API if available, else use canvas
      let base64Image: string

      if ('ImageCapture' in window) {
        const imageCapture = new (window as any).ImageCapture(track)
        const bitmap = await imageCapture.grabFrame()
        const canvas = document.createElement('canvas')
        canvas.width = bitmap.width
        canvas.height = bitmap.height
        const ctx = canvas.getContext('2d')!
        ctx.drawImage(bitmap, 0, 0)
        base64Image = canvas.toDataURL('image/png').split(',')[1]
      } else {
        // Fallback using video element
        const video = document.createElement('video')
        video.srcObject = stream
        await new Promise<void>((resolve) => {
          video.onloadedmetadata = () => {
            video.play()
            resolve()
          }
        })
        await new Promise((resolve) => setTimeout(resolve, 500))
        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        const ctx = canvas.getContext('2d')!
        ctx.drawImage(video, 0, 0)
        base64Image = canvas.toDataURL('image/png').split(',')[1]
        video.pause()
      }

      // Stop all tracks
      stream.getTracks().forEach((t) => t.stop())
      streamRef.current = null

      setLastScreenshot(base64Image)
      return base64Image

    } catch (error) {
      console.error('Screen capture failed:', error)
      return null
    } finally {
      setIsCapturing(false)
    }
  }, [])

  const analyzeScreen = useCallback(async (
    query?: string,
    existingBase64?: string,
  ): Promise<ScreenAnalysis | null> => {
    try {
      const imageBase64 = existingBase64 || await captureScreen()
      if (!imageBase64) return null

      const response = await api.post('/vision/describe', {
        image_base64: imageBase64,
        query: query || null,
      })

      const analysis: ScreenAnalysis = {
        description: response.data.description,
      }

      setLastAnalysis(analysis)
      return analysis

    } catch (error) {
      console.error('Screen analysis failed:', error)
      return null
    }
  }, [captureScreen])

  const captureAndAnalyzeFull = useCallback(async (): Promise<{
    description: string
    app_info: any
    actions: any[]
  } | null> => {
    try {
      const imageBase64 = await captureScreen()
      if (!imageBase64) return null

      const [describeRes, appRes, actionsRes] = await Promise.all([
        api.post('/vision/describe', { image_base64: imageBase64 }),
        api.post('/vision/app-info', { image_base64: imageBase64 }),
        api.post('/vision/suggest-actions', { image_base64: imageBase64 }),
      ])

      return {
        description: describeRes.data.description,
        app_info: appRes.data,
        actions: actionsRes.data.actions,
      }
    } catch (error) {
      console.error('Full screen analysis failed:', error)
      return null
    }
  }, [captureScreen])

  const stopCapture = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setIsCapturing(false)
  }, [])

  return {
    isCapturing,
    lastScreenshot,
    lastAnalysis,
    captureScreen,
    analyzeScreen,
    captureAndAnalyzeFull,
    stopCapture,
  }
}