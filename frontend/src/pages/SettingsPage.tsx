import { useEffect, useState } from 'react'

export default function SettingsPage() {
  const [keys, setKeys] = useState<any>({})
  const [models, setModels] = useState<Record<string, string>>({})
  const [dirs, setDirs] = useState<any[]>([])
  const [googleKey, setGoogleKey] = useState('')
  const [firecrawlKey, setFirecrawlKey] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch('/api/settings/keys').then(r => r.json()).then(setKeys).catch(() => {})
    fetch('/api/settings/models').then(r => r.json()).then(setModels).catch(() => {})
    fetch('/api/settings/directories').then(r => r.json()).then(setDirs).catch(() => {})
  }, [])

  const handleSaveKeys = async () => {
    setSaving(true)
    const body: any = {}
    if (googleKey) body.google_api_key = googleKey
    if (firecrawlKey) body.firecrawl_api_key = firecrawlKey
    await fetch('/api/settings/keys', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    setSaving(false)
    setGoogleKey('')
    setFirecrawlKey('')
    // Reload
    const k = await fetch('/api/settings/keys').then(r => r.json())
    setKeys(k)
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Settings</h2>

      <section className="mb-8">
        <h3 className="text-lg font-semibold text-gray-700 mb-3">API Keys</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Google API Key {keys.google_configured && <span className="text-green-600">(Configured)</span>}
            </label>
            <input
              type="password"
              value={googleKey}
              onChange={(e) => setGoogleKey(e.target.value)}
              placeholder={keys.google_api_key || 'Not set'}
              className="w-full border border-gray-300 rounded-lg p-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Firecrawl API Key {keys.firecrawl_configured && <span className="text-green-600">(Configured)</span>}
            </label>
            <input
              type="password"
              value={firecrawlKey}
              onChange={(e) => setFirecrawlKey(e.target.value)}
              placeholder={keys.firecrawl_api_key || 'Not set'}
              className="w-full border border-gray-300 rounded-lg p-2.5 text-sm"
            />
          </div>
          <button
            onClick={handleSaveKeys}
            disabled={(!googleKey && !firecrawlKey) || saving}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Keys'}
          </button>
        </div>
      </section>

      <section className="mb-8">
        <h3 className="text-lg font-semibold text-gray-700 mb-3">Models</h3>
        <div className="space-y-2">
          {Object.entries(models).map(([key, value]) => (
            <div key={key} className="flex justify-between text-sm py-1 border-b border-gray-100">
              <span className="text-gray-600">{key}</span>
              <span className="font-mono text-gray-800">{value}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold text-gray-700 mb-3">Storage</h3>
        <div className="space-y-2">
          {dirs.map((d: any) => (
            <div key={d.label} className="flex justify-between text-sm py-1 border-b border-gray-100">
              <span className="text-gray-600">{d.label}</span>
              <span className="text-gray-500">{d.file_count} items</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
