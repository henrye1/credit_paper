import { useState, useEffect, useCallback } from 'react'

interface UseSSELogsResult {
  logs: string[]
  status: 'idle' | 'streaming' | 'complete' | 'error'
  clearLogs: () => void
}

export function useSSELogs(assessmentId: string | null): UseSSELogsResult {
  const [logs, setLogs] = useState<string[]>([])
  const [status, setStatus] = useState<'idle' | 'streaming' | 'complete' | 'error'>('idle')

  const clearLogs = useCallback(() => {
    setLogs([])
    setStatus('idle')
  }, [])

  useEffect(() => {
    if (!assessmentId) return

    const source = new EventSource(`/api/assessment/${assessmentId}/logs`)
    setStatus('streaming')

    source.addEventListener('log', (e: MessageEvent) => {
      setLogs(prev => [...prev, e.data])
    })

    source.addEventListener('stage', (e: MessageEvent) => {
      setLogs(prev => [...prev, `\n--- ${e.data} ---`])
    })

    // Ignore heartbeat events (keepalive for proxy compatibility)
    source.addEventListener('heartbeat', () => {})

    source.addEventListener('complete', () => {
      setStatus('complete')
      source.close()
    })

    source.addEventListener('error', (e: MessageEvent) => {
      setLogs(prev => [...prev, `ERROR: ${e.data || 'Connection lost'}`])
      setStatus('error')
      source.close()
    })

    source.onerror = () => {
      if (status !== 'complete') {
        setStatus('error')
      }
      source.close()
    }

    return () => source.close()
  }, [assessmentId])

  return { logs, status, clearLogs }
}
