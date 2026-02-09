import { useEffect, useRef } from 'react'

interface Props {
  logs: string[]
  status: 'idle' | 'streaming' | 'complete' | 'error'
}

export default function LogStream({ logs, status }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs.length])

  return (
    <div className="bg-gray-900 rounded-lg p-4 max-h-[400px] overflow-y-auto font-mono text-xs">
      {logs.length === 0 && status === 'idle' && (
        <p className="text-gray-500">Waiting for logs...</p>
      )}
      {logs.map((line, i) => (
        <div
          key={i}
          className={
            line.startsWith('ERROR')
              ? 'text-red-400'
              : line.startsWith('Warning')
              ? 'text-yellow-400'
              : line.startsWith('\n---')
              ? 'text-blue-400 font-bold mt-2'
              : 'text-green-300'
          }
        >
          {line}
        </div>
      ))}
      {status === 'streaming' && (
        <div className="text-gray-500 animate-pulse mt-1">Processing...</div>
      )}
      {status === 'complete' && (
        <div className="text-blue-400 mt-2 font-bold">Pipeline complete.</div>
      )}
      {status === 'error' && (
        <div className="text-red-400 mt-2 font-bold">Pipeline encountered an error.</div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
