import { useEffect, useState } from 'react'
import type { PromptListItem } from '../types'

export default function PromptEditorPage() {
  const [prompts, setPrompts] = useState<PromptListItem[]>([])
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null)
  const [promptData, setPromptData] = useState<any>(null)
  const [editedSections, setEditedSections] = useState<Record<string, any>>({})
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch('/api/prompts').then(r => r.json()).then(setPrompts).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedPrompt) return
    fetch(`/api/prompts/${selectedPrompt}`)
      .then(r => r.json())
      .then(data => {
        setPromptData(data)
        setEditedSections({})
        const keys = Object.keys(data.sections || {})
        setSelectedKey(keys[0] || null)
      })
      .catch(() => {})
  }, [selectedPrompt])

  const handleFieldChange = (key: string, field: string, value: string) => {
    setEditedSections(prev => ({
      ...prev,
      [key]: {
        ...promptData.sections[key],
        ...(prev[key] || {}),
        [field]: value,
      },
    }))
  }

  const hasChanges = Object.keys(editedSections).length > 0

  const handleSave = async () => {
    if (!selectedPrompt || !hasChanges) return
    setSaving(true)
    const merged: Record<string, any> = {}
    for (const [key, section] of Object.entries(promptData.sections as Record<string, any>)) {
      merged[key] = editedSections[key] || section
    }
    try {
      await fetch(`/api/prompts/${selectedPrompt}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections: merged }),
      })
      // Reload
      const data = await fetch(`/api/prompts/${selectedPrompt}`).then(r => r.json())
      setPromptData(data)
      setEditedSections({})
    } catch (e: any) {
      alert(`Save failed: ${e.message}`)
    }
    setSaving(false)
  }

  const currentSection = selectedKey
    ? (editedSections[selectedKey] || promptData?.sections?.[selectedKey])
    : null

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-4">Prompt Editor</h2>

      <div className="mb-4">
        <select
          value={selectedPrompt || ''}
          onChange={(e) => setSelectedPrompt(e.target.value || null)}
          className="border border-gray-300 rounded-lg p-2.5 text-sm w-80"
        >
          <option value="">Select a prompt...</option>
          {prompts.map(p => (
            <option key={p.name} value={p.name}>{p.label} ({p.section_count} sections)</option>
          ))}
        </select>
      </div>

      {promptData && (
        <div className="flex gap-6">
          {/* Section list */}
          <div className="w-64 space-y-1">
            {Object.entries(promptData.sections as Record<string, any>).map(([key, section]: [string, any]) => {
              const isModified = key in editedSections
              return (
                <button
                  key={key}
                  onClick={() => setSelectedKey(key)}
                  className={`w-full text-left px-3 py-2 text-sm rounded transition-colors ${
                    key === selectedKey ? 'bg-blue-50 text-blue-800 font-medium' : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {isModified && <span className="text-amber-500 mr-1">*</span>}
                  {section.title}
                </button>
              )
            })}
          </div>

          {/* Editor */}
          {currentSection && selectedKey && (
            <div className="flex-1 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input
                  value={currentSection.title}
                  onChange={(e) => handleFieldChange(selectedKey, 'title', e.target.value)}
                  className="w-full border border-gray-300 rounded-lg p-2.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input
                  value={currentSection.description}
                  onChange={(e) => handleFieldChange(selectedKey, 'description', e.target.value)}
                  className="w-full border border-gray-300 rounded-lg p-2.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
                <textarea
                  value={currentSection.content}
                  onChange={(e) => handleFieldChange(selectedKey, 'content', e.target.value)}
                  className="w-full border border-gray-300 rounded-lg p-3 text-sm font-mono min-h-[400px] resize-y"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {hasChanges && (
        <div className="fixed bottom-6 right-6 flex gap-2">
          <button
            onClick={() => setEditedSections({})}
            className="px-4 py-2 text-sm bg-white border border-gray-300 rounded-lg shadow hover:bg-gray-50"
          >
            Discard Changes
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg shadow hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : `Save (${Object.keys(editedSections).length} changed)`}
          </button>
        </div>
      )}
    </div>
  )
}
