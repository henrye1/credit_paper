import { useEffect, useState } from 'react'

interface Report {
  name: string
  size: number
  report_type: string
  company_name: string | null
  created_at: string | null
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)
  const [previewName, setPreviewName] = useState('')

  useEffect(() => {
    fetch('/api/reports')
      .then(r => r.json())
      .then(setReports)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handlePreview = async (filename: string) => {
    try {
      const res = await fetch(`/api/reports/${encodeURIComponent(filename)}/preview`)
      if (!res.ok) throw new Error('Failed to load preview')
      const data = await res.json()
      setPreviewHtml(data.html)
      setPreviewName(filename)
    } catch {
      alert('Failed to load report preview')
    }
  }

  const handleDownload = (filename: string) => {
    const a = document.createElement('a')
    a.href = `/api/reports/${encodeURIComponent(filename)}/download`
    a.download = filename
    a.click()
  }

  const formatSize = (bytes: number) => {
    if (!bytes) return '—'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatDate = (iso: string | null) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleDateString('en-ZA', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Reports</h2>
      <p className="text-gray-600 mb-6">Browse, preview, and download generated assessment reports.</p>

      {loading ? (
        <p className="text-gray-500">Loading reports...</p>
      ) : reports.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-500 mb-2">No reports generated yet.</p>
          <p className="text-sm text-gray-400">
            Complete a Quick Assessment to generate your first report.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map(r => (
            <div key={r.name} className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0 mr-4">
                  <p className="font-medium text-gray-800 truncate">{r.company_name || r.name}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-500 truncate">{r.name}</span>
                    <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                      {r.report_type}
                    </span>
                    <span className="text-xs text-gray-400">{formatSize(r.size)}</span>
                    <span className="text-xs text-gray-400">{formatDate(r.created_at)}</span>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => handlePreview(r.name)}
                    className="px-3 py-1.5 text-sm bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
                  >
                    Preview
                  </button>
                  <button
                    onClick={() => handleDownload(r.name)}
                    className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Download
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview Modal */}
      {previewHtml !== null && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-6">
          <div className="bg-white rounded-lg w-full max-w-5xl h-[85vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="font-medium text-gray-800 truncate">{previewName}</h3>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => handleDownload(previewName)}
                  className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Download
                </button>
                <button
                  onClick={() => { setPreviewHtml(null); setPreviewName('') }}
                  className="px-3 py-1.5 text-sm bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-hidden">
              <iframe
                srcDoc={previewHtml}
                title="Report Preview"
                className="w-full h-full border-0"
                sandbox="allow-same-origin"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
