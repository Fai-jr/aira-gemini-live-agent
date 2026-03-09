import { useState, useEffect, useRef, useCallback } from 'react'
import type { GoalPlan, GoalStep } from '../../store/useAiraStore'
import { useAiraStore } from '../../store/useAiraStore'
import { api } from '../../services/api'

interface AiraGoalPanelProps {
  plan: GoalPlan
  onClose: () => void
}

const stepTypeColors: Record<string, string> = {
  browser:   '#3b82f6',
  search:    '#06b6d4',
  form_fill: '#8b5cf6',
  vision:    '#f59e0b',
  confirm:   '#ef4444',
  general:   '#6c63ff',
}

const stepTypeIcons: Record<string, string> = {
  browser:   '🌐',
  search:    '🔍',
  form_fill: '📝',
  vision:    '👁️',
  confirm:   '✅',
  general:   '⚡',
}

function StepStatusIcon({ status }: { status: GoalStep['status'] }) {
  if (status === 'completed') {
    return (
      <div style={{
        width: '22px', height: '22px', borderRadius: '50%',
        background: '#10b981', display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: '12px', flexShrink: 0, color: 'white',
      }}>✓</div>
    )
  }
  if (status === 'failed') {
    return (
      <div style={{
        width: '22px', height: '22px', borderRadius: '50%',
        background: '#ef4444', display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: '12px', flexShrink: 0, color: 'white',
      }}>✗</div>
    )
  }
  if (status === 'active') {
    return (
      <div style={{
        width: '22px', height: '22px', borderRadius: '50%',
        background: 'var(--aira-accent-primary)', display: 'flex',
        alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        animation: 'blink 1s infinite',
      }}>
        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'white' }} />
      </div>
    )
  }
  return (
    <div style={{
      width: '22px', height: '22px', borderRadius: '50%',
      background: 'var(--aira-bg-elevated)', border: '1px solid var(--aira-border)',
      flexShrink: 0,
    }} />
  )
}

export function AiraGoalPanel({ plan, onClose }: AiraGoalPanelProps) {
  const { updateGoalStep, setCurrentGoal } = useAiraStore()
  const [activeStep, setActiveStep] = useState<number | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [stepError, setStepError] = useState<string | null>(null)
  const [countdown, setCountdown] = useState<number | null>(null)
  const cancelledRef = useRef(false)

  const completedCount = plan.steps.filter(s => s.status === 'completed').length
  const totalCount = plan.steps.length
  const progress = Math.round((completedCount / totalCount) * 100)
  const allDone = completedCount === totalCount && totalCount > 0

  const runStep = useCallback(async (index: number) => {
    if (cancelledRef.current) return
    if (index >= plan.steps.length) {
      setIsRunning(false)
      setActiveStep(null)
      return
    }

    setActiveStep(index)
    setStepError(null)
    updateGoalStep(index, 'active')

    const step = plan.steps[index]

    try {
      if (step.type === 'confirm' || (plan.requires_confirmation && index === plan.steps.length - 1)) {
        setIsPaused(true)
        setIsRunning(false)
        return
      }

      console.log('Executing step:', step)
      const res = await api.post('/browser/execute-step', { step })
      console.log('Step result:', res.data)

      if (res.data.success) {
        updateGoalStep(index, 'completed')
      } else {
        updateGoalStep(index, 'failed')
        setStepError(`Step ${index + 1} failed: ${res.data.error || 'Unknown error'}`)
        await new Promise(r => setTimeout(r, 1000))
      }
    } catch (err: any) {
      console.error('Step error:', err)
      updateGoalStep(index, 'failed')
      setStepError(`Step ${index + 1} error: ${err?.message || 'Network error'}`)
      await new Promise(r => setTimeout(r, 1000))
    }

    if (!cancelledRef.current) {
      await new Promise(r => setTimeout(r, 400))
      await runStep(index + 1)
    }
  }, [plan, updateGoalStep])

  const handleStart = useCallback(async () => {
    cancelledRef.current = false
    setCountdown(null)
    setIsRunning(true)
    setIsPaused(false)
    setStepError(null)
    plan.steps.forEach((_, i) => updateGoalStep(i, 'pending'))
    await new Promise(r => setTimeout(r, 100))
    await runStep(0)
  }, [plan, runStep, updateGoalStep])

  // Auto-execute with 3s countdown
  useEffect(() => {
    if (plan.steps.length === 0) return
    if (plan.requires_confirmation) return

    cancelledRef.current = false
    let count = 3
    setCountdown(count)

    const interval = setInterval(() => {
      count -= 1
      if (count <= 0) {
        clearInterval(interval)
        setCountdown(null)
        handleStart()
      } else {
        setCountdown(count)
      }
    }, 1000)

    return () => {
      clearInterval(interval)
    }
  }, [plan.goal_summary]) // re-run only when a new plan arrives

  const handleCancelCountdown = () => {
    cancelledRef.current = true
    setCountdown(null)
  }

  const handleConfirm = async () => {
    if (activeStep === null) return
    updateGoalStep(activeStep, 'completed')
    setIsPaused(false)
    setIsRunning(true)
    await new Promise(r => setTimeout(r, 200))
    await runStep(activeStep + 1)
  }

  const handleSkipStep = () => {
    if (activeStep === null) return
    updateGoalStep(activeStep, 'completed')
    setIsPaused(false)
    setIsRunning(true)
    runStep(activeStep + 1)
  }

  const handleCancel = async () => {
    cancelledRef.current = true
    if (activeStep !== null) updateGoalStep(activeStep, 'failed')
    setIsRunning(false)
    setIsPaused(false)
    setActiveStep(null)
    setStepError(null)
    setCountdown(null)
    try { await api.post('/browser/stop') } catch { /* ignore */ }
  }

  const handleDismiss = async () => {
    cancelledRef.current = true
    try { await api.post('/browser/stop') } catch { /* ignore */ }
    setCurrentGoal(null)
    onClose()
  }

  return (
    <div className="glass" style={{
      borderRadius: 'var(--radius-lg)',
      padding: '20px',
      animation: 'slideInRight 0.3s ease',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px',
    }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, marginRight: '12px' }}>
          <div style={{
            fontSize: '11px',
            color: 'var(--aira-accent-primary)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontWeight: 600,
            marginBottom: '4px',
          }}>
            Goal Plan
          </div>
          <div style={{
            fontSize: '14px',
            fontWeight: 500,
            color: 'var(--aira-text-primary)',
            lineHeight: '1.4',
          }}>
            {plan.goal_summary}
          </div>
        </div>
        <button onClick={handleDismiss} style={{
          background: 'none', color: 'var(--aira-text-muted)',
          fontSize: '16px', padding: '4px 8px',
          borderRadius: 'var(--radius-sm)', cursor: 'pointer',
          border: '1px solid transparent', lineHeight: 1,
        }}>✕</button>
      </div>

      {/* Countdown banner */}
      {countdown !== null && (
        <div style={{
          padding: '10px 14px', borderRadius: 'var(--radius-sm)',
          background: 'rgba(108,99,255,0.1)', border: '1px solid rgba(108,99,255,0.3)',
          fontSize: '12px', color: 'var(--aira-accent-primary)', fontWeight: 600,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span>⚡ Auto-executing in {countdown}s...</span>
          <button onClick={handleCancelCountdown} style={{
            background: 'none', border: '1px solid rgba(108,99,255,0.3)',
            borderRadius: 'var(--radius-sm)', color: 'var(--aira-accent-primary)',
            fontSize: '11px', padding: '2px 8px', cursor: 'pointer',
          }}>Stop</button>
        </div>
      )}

      {/* Progress bar */}
      {(isRunning || allDone || isPaused) && (
        <div>
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            fontSize: '11px', color: 'var(--aira-text-muted)', marginBottom: '6px',
          }}>
            <span>{allDone ? '✓ Complete!' : isPaused ? 'Waiting for confirmation' : '⚡ Executing...'}</span>
            <span>{completedCount}/{totalCount} steps</span>
          </div>
          <div style={{ height: '4px', background: 'var(--aira-bg-elevated)', borderRadius: '2px', overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${progress}%`,
              background: allDone ? '#10b981' : 'linear-gradient(90deg, var(--aira-accent-primary), var(--aira-accent-cyan))',
              borderRadius: '2px', transition: 'width 0.4s ease',
            }} />
          </div>
        </div>
      )}

      {/* Step error */}
      {stepError && (
        <div style={{
          padding: '8px 12px', borderRadius: 'var(--radius-sm)',
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
          fontSize: '11px', color: '#ef4444',
        }}>{stepError}</div>
      )}

      {/* Confirmation warning */}
      {plan.requires_confirmation && !isRunning && !allDone && (
        <div style={{
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
          borderRadius: 'var(--radius-sm)', padding: '8px 12px',
          fontSize: '12px', color: '#ef4444',
        }}>
          ⚠️ AIRA will ask for confirmation before completing this task
        </div>
      )}

      {/* Steps list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {plan.steps.map((step, index) => (
          <div key={index} style={{
            display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '10px',
            borderRadius: 'var(--radius-sm)',
            background: step.status === 'active' ? 'rgba(108,99,255,0.1)'
              : step.status === 'completed' ? 'rgba(16,185,129,0.07)'
              : step.status === 'failed' ? 'rgba(239,68,68,0.07)'
              : 'var(--aira-bg-secondary)',
            border: `1px solid ${
              step.status === 'active' ? 'rgba(108,99,255,0.3)'
              : step.status === 'completed' ? 'rgba(16,185,129,0.2)'
              : step.status === 'failed' ? 'rgba(239,68,68,0.2)'
              : 'transparent'
            }`,
            transition: 'all 0.3s ease',
            opacity: step.status === 'pending' && isRunning && index > (activeStep ?? -1) ? 0.5 : 1,
          }}>
            <StepStatusIcon status={step.status} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: '13px',
                color: step.status === 'completed' ? 'var(--aira-text-secondary)' : 'var(--aira-text-primary)',
                marginBottom: step.details ? '3px' : '0',
              }}>
                {stepTypeIcons[step.type] || '⚡'} {step.action}
              </div>
              {step.details && (
                <div style={{
                  fontSize: '11px', color: 'var(--aira-text-muted)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{step.details}</div>
              )}
            </div>
            <div style={{
              fontSize: '10px', padding: '2px 6px',
              borderRadius: 'var(--radius-full)',
              background: `${stepTypeColors[step.type] || '#6c63ff'}22`,
              color: stepTypeColors[step.type] || '#6c63ff',
              fontWeight: 600, flexShrink: 0, textTransform: 'uppercase',
              letterSpacing: '0.05em', alignSelf: 'flex-start',
            }}>{step.type}</div>
          </div>
        ))}
      </div>

      {/* Buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {!isRunning && !isPaused && !allDone && countdown === null && (
          <button onClick={handleStart} style={{
            padding: '10px', borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-blue))',
            color: 'white', fontSize: '13px', fontWeight: 600, cursor: 'pointer', border: 'none',
          }}>▶ Start Executing Plan</button>
        )}

        {isRunning && !isPaused && (
          <button onClick={handleCancel} style={{
            padding: '10px', borderRadius: 'var(--radius-md)',
            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
            color: '#ef4444', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
          }}>✕ Cancel</button>
        )}

        {isPaused && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={handleConfirm} style={{
              flex: 1, padding: '10px', borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, #10b981, #059669)',
              color: 'white', fontSize: '13px', fontWeight: 600, cursor: 'pointer', border: 'none',
            }}>✓ Confirm</button>
            <button onClick={handleSkipStep} style={{
              padding: '10px 14px', borderRadius: 'var(--radius-md)',
              background: 'var(--aira-bg-elevated)', border: '1px solid var(--aira-border)',
              color: 'var(--aira-text-secondary)', fontSize: '13px', cursor: 'pointer',
            }}>Skip</button>
            <button onClick={handleCancel} style={{
              padding: '10px 14px', borderRadius: 'var(--radius-md)',
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
              color: '#ef4444', fontSize: '13px', cursor: 'pointer',
            }}>Cancel</button>
          </div>
        )}

        {allDone && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{
              padding: '10px', borderRadius: 'var(--radius-md)',
              background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
              color: '#10b981', fontSize: '13px', fontWeight: 600, textAlign: 'center',
            }}>✓ All steps completed!</div>
            <button onClick={handleDismiss} style={{
              padding: '8px', borderRadius: 'var(--radius-md)',
              background: 'var(--aira-bg-elevated)', border: '1px solid var(--aira-border)',
              color: 'var(--aira-text-secondary)', fontSize: '12px', cursor: 'pointer',
            }}>Dismiss</button>
          </div>
        )}
      </div>
    </div>
  )
}