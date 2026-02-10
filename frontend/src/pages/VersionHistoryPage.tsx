import { useEffect, useState } from 'react'
import type { PromptListItem, PromptSet } from '../types'
import { listPromptSets } from '../api/promptSets'

export default function VersionHistoryPage() {
  const [promptSets, setPromptSets] = useState<PromptSet[]>([])
  const [activeSet, setActiveSet] = useState<string>('')
  const [prompts, setPrompts] = useState<PromptListItem[]>([])
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null)
  const [versions, setVersions] = useState<{ timestamp: string; display_time: string }[]>([])
  const [viewingVersion, setViewingVersion] = useState<any>(null)

  // Fetch prompt sets on mount
  useEffect(() => {
    listPromptSets().then(sets => {
      setPromptSets(sets)
      const defaultSet = sets.find(s => s.is_default)
      if (defaultSet) setActiveSet(defaultSet.slug)
    }).catch(() => {})
  }, [])

  // Fetch prompt list when set changes
  useEffect(() => {
    if (!activeSet) return
    fetch(`/api/prompts?set=${activeSet}`).then(r => r.json()).then(setPrompts).catch(() => {})
    setSelectedPrompt(null)
    setVersions([])
    setViewingVersion(null)
  }, [activeSet])

  useEffect(() => {
    if (!selectedPrompt || !activeSet) return
    fetch(`/api/prompts/${selectedPrompt}/versions?set=${activeSet}`)
      .then(r => r.json())
      .then(setVersions)
      .catch(() => {})
  }, [selectedPrompt, activeSet])

  const handleView = async (ts: string) => {
    if (!selectedPrompt) return
    const data = await fetch(`/api/prompts/${selectedPrompt}/versions/${ts}?set=${activeSet}`).then(r => r.json())
    setViewingVersion(data)
  }

  const handleRevert = async (ts: string) => {
    if (!selectedPrompt) return
    if (!confirm('Revert to this version? A new version will be created.')) return
    await fetch(`/api/prompts/${selectedPrompt}/revert/${ts}?set=${activeSet}`, { method: 'POST' })
    // Reload versions
    const v = await fetch(`/api/prompts/${selectedPrompt}/versions?set=${activeSet}`).then(r => r.json())
    setVersions(v)
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-4">Version History</h2>

      {/* Prompt Set selector */}
      <div className="mb-4">
        <label className="block text-xs font-medium text-gray-500 mb-1">Prompt Set</label>
        <select
          value={activeSet}
          onChange={(e) => setActiveSet(e.target.value)}
          className="border border-gray-300 rounded-lg p-2.5 text-sm w-60"
        >
          {promptSets.map(s => (
            <option key={s.slug} value={s.slug}>
              {s.display_name}{s.is_default ? ' (default)' : ''}
            </option>
          ))}
        </select>
      </div>

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
