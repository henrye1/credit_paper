import { useEffect, useRef, useState } from 'react'

interface Example {
  prefix: string
  display_name: string
  files: { name: string; size: number; type: string }[]
}

export default function ExamplesPage() {
  const [examples, setExamples] = useState<Example[]>([])
  const [deleting, setDeleting] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [mdFile, setMdFile] = useState<File | null>(null)
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [xlsxFile, setXlsxFile] = useState<File | null>(null)
  const mdRef = useRef<HTMLInputElement>(null)
  const pdfRef = useRef<HTMLInputElement>(null)
  const xlsxRef = useRef<HTMLInputElement>(null)

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

  const resetUpload = () => {
    setMdFile(null)
    setPdfFile(null)
    setXlsxFile(null)
    setUploadError(null)
    if (mdRef.current) mdRef.current.value = ''
    if (pdfRef.current) pdfRef.current.value = ''
    if (xlsxRef.current) xlsxRef.current.value = ''
  }

  const handleUpload = async () => {
    if (!mdFile || !pdfFile) return
    setUploading(true)
    setUploadError(null)
    try {
      const form = new FormData()
      form.append('md_file', mdFile)
      form.append('pdf_file', pdfFile)
      if (xlsxFile) form.append('xlsx_file', xlsxFile)
      const res = await fetch('/api/examples/', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(err.detail || 'Upload failed')
      }
      resetUpload()
      load()
    } catch (e: any) {
      setUploadError(e.message)
    }
    setUploading(false)
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Few-Shot Examples</h2>
      <p className="text-gray-600 mb-6">Manage learning example pairs used for report generation.</p>

      {/* Upload section */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Upload New Example</h3>
        <p className="text-xs text-gray-500 mb-4">
          Files must start with a numeric prefix (e.g., "34. Company Name.md"). The MD and PDF prefixes must match.
        </p>
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Markdown File (.md) <span className="text-red-500">*</span>
            </label>
            <div
              onClick={() => mdRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-3 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
            >
              <input ref={mdRef} type="file" accept=".md" onChange={(e) => setMdFile(e.target.files?.[0] || null)} className="hidden" />
              <p className="text-xs text-gray-500 truncate">{mdFile ? mdFile.name : 'Click to select'}</p>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              PDF File (.pdf) <span className="text-red-500">*</span>
            </label>
            <div
              onClick={() => pdfRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-3 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
            >
              <input ref={pdfRef} type="file" accept=".pdf" onChange={(e) => setPdfFile(e.target.files?.[0] || null)} className="hidden" />
              <p className="text-xs text-gray-500 truncate">{pdfFile ? pdfFile.name : 'Click to select'}</p>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Excel File (.xlsx) <span className="text-gray-400">(optional)</span>
            </label>
            <div
              onClick={() => xlsxRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-3 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
            >
              <input ref={xlsxRef} type="file" accept=".xlsx,.xlsm" onChange={(e) => setXlsxFile(e.target.files?.[0] || null)} className="hidden" />
              <p className="text-xs text-gray-500 truncate">{xlsxFile ? xlsxFile.name : 'Click to select'}</p>
            </div>
          </div>
        </div>
        {uploadError && (
          <p className="text-xs text-red-600 mb-3">{uploadError}</p>
        )}
        <div className="flex gap-2">
          <button
            onClick={handleUpload}
            disabled={!mdFile || !pdfFile || uploading}
            className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? 'Uploading...' : 'Upload Example'}
          </button>
          {(mdFile || pdfFile || xlsxFile) && (
            <button onClick={resetUpload} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Examples list */}
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
