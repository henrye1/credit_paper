import { useEffect, useState } from 'react'

interface Example {
  prefix: string
  display_name: string
  files: { name: string; size: number; type: string }[]
}

export default function ExamplesPage() {
  const [examples, setExamples] = useState<Example[]>([])
  const [deleting, setDeleting] = useState<string | null>(null)

  const load = () => {
    fetch('/api/examples').then(r => r.json()).then(setExamples).catch(() => {})
  }

  useEffect(load, [])

  const handleDelete = async (prefix: string) => {
    if (!confirm(`Delete example ${prefix}?`)) return
    setDeleting(prefix)
    await fetch(`/api/examples/${prefix}`, { method: 'DELETE' })
    setDeleting(null)
    load()
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Few-Shot Examples</h2>
      <p className="text-gray-600 mb-6">Manage learning example pairs used for report generation.</p>

      {examples.length === 0 ? (
        <p className="text-gray-500">No examples found.</p>
      ) : (
        <div className="space-y-3">
          {examples.map(ex => (
            <div key={ex.prefix} className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-mono text-gray-400 mr-2">{ex.prefix}.</span>
                  <span className="font-medium text-gray-800">{ex.display_name}</span>
                </div>
                <button
                  onClick={() => handleDelete(ex.prefix)}
                  disabled={deleting === ex.prefix}
                  className="text-sm text-red-600 hover:text-red-800"
                >
                  {deleting === ex.prefix ? 'Deleting...' : 'Remove'}
                </button>
              </div>
              <div className="mt-2 flex gap-4">
                {ex.files.map(f => (
                  <span key={f.name} className="text-xs text-gray-500">
                    {f.name} ({(f.size / 1024).toFixed(0)} KB)
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
