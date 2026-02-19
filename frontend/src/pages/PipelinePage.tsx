import { useRef, useState } from 'react'
import LogStream from '../components/pipeline/LogStream'
import { useSSELogs } from '../hooks/useSSELogs'

const STAGES = [
  { id: 'parse', label: '1. Parse Excel to Markdown' },
  { id: 'business_desc', label: '2. Extract Business Description' },
  { id: 'generate', label: '3. Generate Financial Report' },
  { id: 'audit', label: '4. Audit LLM Review' },
  { id: 'compare', label: '5. Compare Human vs LLM' },
  { id: 'convert', label: '6. Convert to DOCX/JSON' },
]

export default function PipelinePage() {
  const [selectedStages, setSelectedStages] = useState<string[]>(['parse', 'business_desc', 'generate'])
  const [modelReport, setModelReport] = useState('gemini-2.5-flash')
  const [modelAudit, setModelAudit] = useState('gemini-2.5-flash')
  const [runId, setRunId] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { logs, status } = useSSELogs(runId)

  const toggleStage = (id: string) => {
    setSelectedStages(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files))
    }
  }

  const handleRun = async () => {
    setRunning(true)
    try {
      const form = new FormData()
      form.append('stages', selectedStages.join(','))
      form.append('model_report', modelReport)
      form.append('model_audit', modelAudit)
      for (const f of files) {
        form.append('files', f)
      }
      const res = await fetch('/api/pipeline/run', { method: 'POST', body: form })
      const data = await res.json()
      setRunId(data.run_id)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      alert(`Error: ${msg}`)
    }
    setRunning(false)
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Dev Pipeline</h2>
      <p className="text-gray-600 mb-6">Upload files and run individual pipeline stages.</p>

      <div className="space-y-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Input Files</label>
          <p className="text-xs text-gray-500 mb-2">Upload Excel (.xlsx/.xlsm), PDF, and DOCX files for processing.</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".xlsx,.xlsm,.pdf,.docx,.txt"
            onChange={handleFileChange}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          {files.length > 0 && (
            <p className="text-xs text-gray-500 mt-1">{files.length} file(s) selected</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Select Stages</label>
          <div className="space-y-2">
            {STAGES.map(stage => (
              <label key={stage.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedStages.includes(stage.id)}
                  onChange={() => toggleStage(stage.id)}
                  className="rounded"
                />
                {stage.label}
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Report Model</label>
            <select
              value={modelReport}
              onChange={(e) => setModelReport(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2 text-sm"
            >
              <option value="gemini-2.5-flash">gemini-2.5-flash</option>
              <option value="gemini-2.5-pro">gemini-2.5-pro</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Audit Model</label>
            <select
              value={modelAudit}
              onChange={(e) => setModelAudit(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2 text-sm"
            >
              <option value="gemini-2.5-flash">gemini-2.5-flash</option>
              <option value="gemini-2.5-pro">gemini-2.5-pro</option>
            </select>
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={selectedStages.length === 0 || running || status === 'streaming'}
          className="w-full py-2.5 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {running ? 'Starting...' : 'Run Pipeline'}
        </button>
      </div>

      {(logs.length > 0 || runId) && (
        <LogStream logs={logs} status={status} />
      )}
    </div>
  )
}
