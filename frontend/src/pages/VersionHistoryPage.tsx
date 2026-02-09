import { useEffect, useState } from 'react'
import type { PromptListItem } from '../types'

export default function VersionHistoryPage() {
  const [prompts, setPrompts] = useState<PromptListItem[]>([])
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null)
  const [versions, setVersions] = useState<{ timestamp: string; display_time: string }[]>([])
  const [viewingVersion, setViewingVersion] = useState<any>(null)

  useEffect(() => {
    fetch('/api/prompts').then(r => r.json()).then(setPrompts).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedPrompt) return
    fetch(`/api/prompts/${selectedPrompt}/versions`)
      .then(r => r.json())
      .then(setVersions)
      .catch(() => {})
  }, [selectedPrompt])

  const handleView = async (ts: string) => {
    if (!selectedPrompt) return
    const data = await fetch(`/api/prompts/${selectedPrompt}/versions/${ts}`).then(r => r.json())
    setViewingVersion(data)
  }

  const handleRevert = async (ts: string) => {
    if (!selectedPrompt) return
    if (!confirm('Revert to this version? A new version will be created.')) return
    await fetch(`/api/prompts/${selectedPrompt}/revert/${ts}`, { method: 'POST' })
    // Reload versions
    const v = await fetch(`/api/prompts/${selectedPrompt}/versions`).then(r => r.json())
    setVersions(v)
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-4">Version History</h2>

      <select
        value={selectedPrompt || ''}
        onChange={(e) => { setSelectedPrompt(e.target.value || null); setViewingVersion(null) }}
        className="border border-gray-300 rounded-lg p-2.5 text-sm w-80 mb-6"
      >
        <option value="">Select a prompt...</option>
        {prompts.map(p => (
          <option key={p.name} value={p.name}>{p.label}</option>
        ))}
      </select>

      {versions.length > 0 && (
        <div className="space-y-2">
          {versions.map(v => (
            <div key={v.timestamp} className="flex items-center justify-between bg-white border border-gray-200 rounded-lg px-4 py-3">
              <span className="text-sm text-gray-700">{v.display_time}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => handleView(v.timestamp)}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  View
                </button>
                <button
                  onClick={() => handleRevert(v.timestamp)}
                  className="text-sm text-amber-600 hover:text-amber-800"
                >
                  Revert
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {viewingVersion && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold mb-3">Version Details</h3>
          {Object.entries(viewingVersion.sections || {}).map(([key, section]: [string, any]) => (
            <div key={key} className="mb-4 bg-white border border-gray-200 rounded-lg p-4">
              <h4 className="font-medium text-gray-800">{section.title}</h4>
              <pre className="mt-2 text-xs text-gray-600 whitespace-pre-wrap max-h-40 overflow-y-auto">
                {section.content?.substring(0, 500)}
                {section.content?.length > 500 ? '...' : ''}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
