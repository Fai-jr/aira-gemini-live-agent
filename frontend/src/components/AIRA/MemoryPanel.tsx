import { useState, useEffect, useCallback } from 'react'
import { api } from '../../services/api'

interface Memory {
  id: string
  memory_type: string
  content: string
  key: string | null
  relevance_score: number
  is_pinned: boolean
  created_at: string
  updated_at: string
}

const typeColors: Record<string, string> = {
  preference: '#6c63ff',
  fact:       '#06b6d4',
  habit:      '#f59e0b',
  correction: '#ef4444',
  goal:       '#10b981',
  context:    '#8b5cf6',
}

const typeIcons: Record<string, string> = {
  preference: '⚙️',
  fact:       '📌',
  habit:      '🔄',
  correction: '✏️',
  goal:       '🎯',
  context:    '💡',
}

export function MemoryPanel() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [adding, setAdding] = useState(false)
  const [newMemory, setNewMemory] = useState({ type: 'fact', content: '', key: '' })
  const [saving, setSaving] = useState(false)

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const params: Record<string, any> = { limit: 100 }
      if (filter !== 'all') params.memory_type = filter
      const res = await api.get('/memory/', { params })
      setMemories(res.data)
    } catch {
      setError('Failed to load memories.')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { fetchMemories() }, [fetchMemories])

  const handlePin = async (memory: Memory) => {
    try {
      await api.patch(`/memory/${memory.id}`, { is_pinned: !memory.is_pinned })
      setMemories(prev => prev.map(m =>
        m.id === memory.id ? { ...m, is_pinned: !m.is_pinned } : m
      ))
    } catch {
      setError('Failed to update memory.')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/memory/${id}`)
      setMemories(prev => prev.filter(m => m.id !== id))
    } catch {
      setError('Failed to delete memory.')
    }
  }

  const handleEdit = (memory: Memory) => {
    setEditingId(memory.id)
    setEditContent(memory.content)
  }

  const handleSaveEdit = async (id: string) => {
    if (!editContent.trim()) return
    setSaving(true)
    try {
      await api.patch(`/memory/${id}`, { content: editContent.trim() })
      setMemories(prev => prev.map(m =>
        m.id === id ? { ...m, content: editContent.trim() } : m
      ))
      setEditingId(null)
    } catch {
      setError('Failed to save edit.')
    } finally {
      setSaving(false)
    }
  }

  const handleAdd = async () => {
    if (!newMemory.content.trim()) return
    setSaving(true)
    try {
      const res = await api.post('/memory/', {
        memory_type: newMemory.type,
        content: newMemory.content.trim(),
        key: newMemory.key.trim() || null,
        is_pinned: false,
      })
      setMemories(prev => [res.data, ...prev])
      setNewMemory({ type: 'fact', content: '', key: '' })
      setAdding(false)
    } catch {
      setError('Failed to add memory.')
    } finally {
      setSaving(false)
    }
  }

  const pinned = memories.filter(m => m.is_pinned)
  const unpinned = memories.filter(m => !m.is_pinned)
  const types = ['all', 'preference', 'fact', 'habit', 'correction', 'goal', 'context']

  const card = {
    background: 'var(--aira-bg-elevated)',
    border: '1px solid var(--aira-border)',
    borderRadius: 'var(--radius-md)',
    padding: '12px 14px',
  }

  const btn = (variant: 'primary' | 'ghost' | 'danger' = 'ghost') => ({
    padding: '5px 10px',
    borderRadius: 'var(--radius-sm)',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
    border: variant === 'primary' ? 'none' : '1px solid var(--aira-border)',
    background: variant === 'primary'
      ? 'linear-gradient(135deg, var(--aira-accent-primary), var(--aira-accent-blue))'
      : variant === 'danger'
      ? 'rgba(239,68,68,0.1)'
      : 'var(--aira-bg-secondary)',
    color: variant === 'primary' ? 'white'
      : variant === 'danger' ? '#ef4444'
      : 'var(--aira-text-secondary)',
  })

  const renderMemory = (memory: Memory) => (
    <div key={memory.id} style={{
      ...card,
      borderLeft: `3px solid ${typeColors[memory.memory_type] || '#6c63ff'}`,
      opacity: editingId && editingId !== memory.id ? 0.5 : 1,
      transition: 'opacity 0.2s',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
        {/* Type icon + badge */}
        <div style={{ flexShrink: 0, marginTop: '2px' }}>
          <span style={{ fontSize: '16px' }}>{typeIcons[memory.memory_type] || '💡'}</span>
        </div>

        {/* Content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {editingId === memory.id ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <textarea
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  background: 'var(--aira-bg-secondary)',
                  border: '1px solid var(--aira-accent-primary)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--aira-text-primary)',
                  fontSize: '13px',
                  padding: '8px',
                  resize: 'vertical',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
                autoFocus
              />
              <div style={{ display: 'flex', gap: '6px' }}>
                <button onClick={() => handleSaveEdit(memory.id)} disabled={saving} style={btn('primary')}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button onClick={() => setEditingId(null)} style={btn()}>Cancel</button>
              </div>
            </div>
          ) : (
            <>
              <div style={{ fontSize: '13px', color: 'var(--aira-text-primary)', lineHeight: '1.5', marginBottom: '4px' }}>
                {memory.content}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span style={{
                  fontSize: '10px',
                  padding: '2px 6px',
                  borderRadius: 'var(--radius-full)',
                  background: `${typeColors[memory.memory_type] || '#6c63ff'}22`,
                  color: typeColors[memory.memory_type] || '#6c63ff',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}>
                  {memory.memory_type}
                </span>
                {memory.key && (
                  <span style={{ fontSize: '11px', color: 'var(--aira-text-muted)' }}>
                    #{memory.key}
                  </span>
                )}
                <span style={{ fontSize: '11px', color: 'var(--aira-text-muted)', marginLeft: 'auto' }}>
                  {new Date(memory.updated_at).toLocaleDateString()}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Actions */}
        {editingId !== memory.id && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flexShrink: 0 }}>
            <button
              onClick={() => handlePin(memory)}
              title={memory.is_pinned ? 'Unpin' : 'Pin'}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '14px',
                opacity: memory.is_pinned ? 1 : 0.3,
                padding: '2px',
              }}
            >
              📍
            </button>
            <button
              onClick={() => handleEdit(memory)}
              title="Edit"
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px', padding: '2px', opacity: 0.6 }}
            >
              ✏️
            </button>
            <button
              onClick={() => handleDelete(memory.id)}
              title="Delete"
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px', padding: '2px', opacity: 0.6 }}
            >
              🗑️
            </button>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--aira-accent-primary)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            AIRA's Memory
          </div>
          <div style={{ fontSize: '12px', color: 'var(--aira-text-muted)', marginTop: '2px' }}>
            {memories.length} {memories.length === 1 ? 'memory' : 'memories'} stored
          </div>
        </div>
        <button
          onClick={() => setAdding(!adding)}
          style={btn('primary')}
        >
          {adding ? 'Cancel' : '+ Add'}
        </button>
      </div>

      {/* Add new memory form */}
      {adding && (
        <div style={{ ...card, border: '1px solid rgba(108,99,255,0.4)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--aira-accent-primary)' }}>New Memory</div>
          <select
            value={newMemory.type}
            onChange={e => setNewMemory(p => ({ ...p, type: e.target.value }))}
            style={{
              background: 'var(--aira-bg-secondary)',
              border: '1px solid var(--aira-border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--aira-text-primary)',
              fontSize: '13px',
              padding: '7px 10px',
              outline: 'none',
            }}
          >
            {['preference', 'fact', 'habit', 'correction', 'goal', 'context'].map(t => (
              <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
            ))}
          </select>
          <input
            placeholder="Key (optional, e.g. preferred_language)"
            value={newMemory.key}
            onChange={e => setNewMemory(p => ({ ...p, key: e.target.value }))}
            style={{
              background: 'var(--aira-bg-secondary)',
              border: '1px solid var(--aira-border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--aira-text-primary)',
              fontSize: '13px',
              padding: '7px 10px',
              outline: 'none',
            }}
          />
          <textarea
            placeholder="What should AIRA remember?"
            value={newMemory.content}
            onChange={e => setNewMemory(p => ({ ...p, content: e.target.value }))}
            rows={3}
            style={{
              background: 'var(--aira-bg-secondary)',
              border: '1px solid var(--aira-border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--aira-text-primary)',
              fontSize: '13px',
              padding: '7px 10px',
              outline: 'none',
              resize: 'vertical',
              width: '100%',
              boxSizing: 'border-box',
            }}
          />
          <button
            onClick={handleAdd}
            disabled={saving || !newMemory.content.trim()}
            style={btn('primary')}
          >
            {saving ? 'Saving...' : 'Save Memory'}
          </button>
        </div>
      )}

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {types.map(t => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            style={{
              padding: '4px 10px',
              borderRadius: 'var(--radius-full)',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
              border: filter === t
                ? `1px solid ${typeColors[t] || 'var(--aira-accent-primary)'}`
                : '1px solid var(--aira-border)',
              background: filter === t
                ? `${typeColors[t] || 'var(--aira-accent-primary)'}22`
                : 'transparent',
              color: filter === t
                ? (typeColors[t] || 'var(--aira-accent-primary)')
                : 'var(--aira-text-muted)',
              textTransform: 'capitalize',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '10px 14px',
          borderRadius: 'var(--radius-md)',
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          color: '#ef4444',
          fontSize: '12px',
        }}>
          {error}
        </div>
      )}

      {/* Memory list */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', color: 'var(--aira-text-muted)', fontSize: '13px', padding: '32px' }}>
            Loading memories...
          </div>
        ) : memories.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--aira-text-muted)', fontSize: '13px', padding: '32px' }}>
            {filter === 'all'
              ? 'No memories yet. Talk to AIRA and she will remember things about you.'
              : `No ${filter} memories yet.`}
          </div>
        ) : (
          <>
            {/* Pinned section */}
            {pinned.length > 0 && (
              <>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--aira-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', padding: '4px 0' }}>
                  📍 Pinned
                </div>
                {pinned.map(renderMemory)}
                {unpinned.length > 0 && (
                  <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--aira-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', padding: '4px 0', marginTop: '4px' }}>
                    All Memories
                  </div>
                )}
              </>
            )}
            {unpinned.map(renderMemory)}
          </>
        )}
      </div>
    </div>
  )
}