import { useState, useRef } from 'react'
import ReportPreview from './ReportPreview'

interface Props {
  assessmentId: string
  sectionIdx: number
  headHtml: string
  currentHtml: string
  pendingProposal?: string
  onAccept: (html: string) => void
  onReject: () => void
}

export default function AiUpdatePanel({
  assessmentId, sectionIdx, headHtml, currentHtml,
  pendingProposal, onAccept, onReject,
}: Props) {
  const [instruction, setInstruction] = useState('')
  const [includeContext, setIncludeContext] = useState(false)
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [proposal, setProposal] = useState<string | null>(pendingProposal || null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleGenerate = async () => {
    if (!instruction.trim()) return
    setLoading(true)
    setError(null)

    try {
      const { aiUpdateSection } = await import('../../api/assessment')
      const result = await aiUpdateSection(
        assessmentId, sectionIdx, instruction, includeContext, evidenceFiles
      )
      if (result.success) {
        setProposal(result.proposed_html)
      } else {
        setError(result.message)
      }
    } catch (e: any) {
      setError(e.message || 'AI update failed')
    } finally {
      setLoading(false)
    }
  }

  const handleAccept = () => {
    if (proposal) {
      onAccept(proposal)
      setProposal(null)
      setInstruction('')
      setEvidenceFiles([])
    }
  }

  const handleReject = () => {
    setProposal(null)
    onReject()
  }

  // If there's a pending proposal, show governance gate
  if (proposal) {
    return (
      <div>
        <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-sm font-medium text-amber-800">
            Review the AI-generated update before accepting.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <h4 className="text-sm font-medium text-gray-600 mb-2">Current</h4>
            <ReportPreview html={currentHtml} headHtml={headHtml} height={350} />
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-600 mb-2">Proposed</h4>
            <ReportPreview html={proposal} headHtml={headHtml} height={350} />
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleAccept}
            className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 font-medium"
          >
            Accept Changes
          </button>
          <button
            onClick={handleReject}
            className="px-4 py-2 text-sm bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
          >
            Reject
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <p className="text-sm text-gray-600 mb-3">
        Describe what you want changed. Optionally upload evidence for the AI to reference.
      </p>

      {/* Evidence files */}
      <div className="mb-3">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Additional evidence (optional)
        </label>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.xlsx"
          onChange={(e) => setEvidenceFiles(Array.from(e.target.files || []))}
          className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-medium file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
        />
        {evidenceFiles.length > 0 && (
          <p className="text-xs text-gray-500 mt-1">
            {evidenceFiles.length} file(s) selected
          </p>
        )}
      </div>

      {/* Instruction */}
      <textarea
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        placeholder="e.g., Update the profitability analysis to reflect the Q4 2024 results from the attached PDF."
        className="w-full border border-gray-300 rounded-lg p-3 text-sm resize-y min-h-[100px] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />

      <div className="flex items-center gap-4 mt-3">
        <button
          onClick={handleGenerate}
          disabled={!instruction.trim() || loading}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          {loading ? 'Generating...' : 'Update with AI'}
        </button>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={includeContext}
            onChange={(e) => setIncludeContext(e.target.checked)}
            className="rounded"
          />
          Include full report context
        </label>
      </div>

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}
    </div>
  )
}
