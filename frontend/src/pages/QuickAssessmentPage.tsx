import { useState, useCallback } from 'react'
import { useAssessmentStore } from '../store/assessmentStore'
import { useSSELogs } from '../hooks/useSSELogs'
import * as api from '../api/assessment'
import FileUploader from '../components/upload/FileUploader'
import LogStream from '../components/pipeline/LogStream'
import ReportPreview from '../components/report/ReportPreview'
import SectionSelector from '../components/report/SectionSelector'
import SectionEditor from '../components/report/SectionEditor'
import AiUpdatePanel from '../components/report/AiUpdatePanel'

export default function QuickAssessmentPage() {
  const store = useAssessmentStore()

  switch (store.phase) {
    case 'upload':
      return <UploadView />
    case 'generating':
      return <GeneratingView />
    case 'review':
      return <ReviewView />
    case 'complete':
      return <CompleteView />
  }
}

// ────────────────────────────────────────────────────────────────
// Upload View
// ────────────────────────────────────────────────────────────────

function UploadView() {
  const store = useAssessmentStore()
  const [ratioFiles, setRatioFiles] = useState<File[]>([])
  const [pdfFiles, setPdfFiles] = useState<File[]>([])
  const [model, setModel] = useState('gemini-2.5-flash')
  const [skipBizDesc, setSkipBizDesc] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const canRun = ratioFiles.length > 0 && pdfFiles.length > 0

  const handleGenerate = async () => {
    if (!canRun) return
    setSubmitting(true)
    try {
      const { assessment_id } = await api.startAssessment(
        ratioFiles[0], pdfFiles, model, skipBizDesc
      )
      store.setAssessmentId(assessment_id)
      store.setModelChoice(model)
      store.setPhase('generating')
    } catch (e: any) {
      alert(`Error: ${e.message}`)
      setSubmitting(false)
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Quick Assessment</h2>
      <p className="text-gray-600 mb-6">
        Upload your Excel ratio file and AFS PDFs, then generate a complete financial condition assessment report.
      </p>

      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-6">
          <FileUploader
            label="Financial Ratio File (.xlsx / .xlsm)"
            accept=".xlsx,.xlsm"
            files={ratioFiles}
            onChange={setRatioFiles}
            required
          />
          <FileUploader
            label="Audited Financial Statements (.pdf)"
            accept=".pdf"
            multiple
            files={pdfFiles}
            onChange={setPdfFiles}
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Report Generation Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2.5 text-sm bg-white"
            >
              <option value="gemini-2.5-flash">gemini-2.5-flash</option>
              <option value="gemini-2.5-pro">gemini-2.5-pro (requires billing)</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-gray-700 pb-2.5">
              <input
                type="checkbox"
                checked={skipBizDesc}
                onChange={(e) => setSkipBizDesc(e.target.checked)}
                className="rounded"
              />
              Skip business description extraction
            </label>
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={!canRun || submitting}
          className="w-full py-3 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? 'Starting...' : 'Generate Report'}
        </button>
      </div>
    </div>
  )
}

// ────────────────────────────────────────────────────────────────
// Generating View
// ────────────────────────────────────────────────────────────────

function GeneratingView() {
  const store = useAssessmentStore()
  const { logs, status } = useSSELogs(store.assessmentId)

  // When generation completes, fetch sections and transition to review
  const handleComplete = useCallback(async () => {
    if (!store.assessmentId) return
    try {
      const data = await api.getSections(store.assessmentId)
      store.setSections(data.head_html, data.sections)
      store.setPhase('review')
    } catch (e: any) {
      alert(`Error loading sections: ${e.message}`)
    }
  }, [store.assessmentId])

  // Auto-transition on complete
  if (status === 'complete' && store.phase === 'generating') {
    handleComplete()
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Generating Report</h2>
      <p className="text-gray-600 mb-4">
        Processing your files and generating the financial condition assessment report...
      </p>

      <div className="mb-4">
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all ${
              status === 'error' ? 'bg-red-500' : 'bg-blue-600'
            } ${status === 'streaming' ? 'animate-pulse' : ''}`}
            style={{
              width: status === 'complete' ? '100%'
                : status === 'error' ? '100%'
                : '60%',
            }}
          />
        </div>
      </div>

      <LogStream logs={logs} status={status} />

      {status === 'error' && (
        <button
          onClick={() => store.reset()}
          className="mt-4 px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
        >
          Back to Upload
        </button>
      )}
    </div>
  )
}

// ────────────────────────────────────────────────────────────────
// Review View
// ────────────────────────────────────────────────────────────────

function ReviewView() {
  const store = useAssessmentStore()
  const [activeTab, setActiveTab] = useState<'edit' | 'ai'>('edit')
  const section = store.sections[store.selectedSectionIndex]

  if (!section) return null

  const handleApprove = async () => {
    if (!store.assessmentId) return
    await api.approveSection(store.assessmentId, store.selectedSectionIndex)
    store.updateSectionStatus(store.selectedSectionIndex, 'approved')
    store.advanceToNextUnapproved()
  }

  const handleReset = async () => {
    if (!store.assessmentId) return
    await api.resetSection(store.assessmentId, store.selectedSectionIndex)
    store.updateSectionHtml(store.selectedSectionIndex, section.original_html)
    store.updateSectionStatus(store.selectedSectionIndex, 'pending')
    store.clearAiProposal(store.selectedSectionIndex)
  }

  const handleApplyEdit = async (html: string) => {
    if (!store.assessmentId) return
    await api.updateSection(store.assessmentId, store.selectedSectionIndex, html)
    store.updateSectionHtml(store.selectedSectionIndex, html)
  }

  const handleApproveAll = async () => {
    if (!store.assessmentId) return
    await api.approveAllSections(store.assessmentId)
    store.sections.forEach((_, i) => store.updateSectionStatus(i, 'approved'))
  }

  const handleFinalize = async () => {
    if (!store.assessmentId) return
    try {
      const result = await api.finalizeAssessment(store.assessmentId)
      if (result.success) {
        store.setReportName(result.report_name)
        store.setPhase('complete')
      }
    } catch (e: any) {
      alert(`Finalize failed: ${e.message}`)
    }
  }

  const handleDiscard = async () => {
    if (!store.assessmentId) return
    if (!confirm('Discard this assessment? This cannot be undone.')) return
    await api.discardAssessment(store.assessmentId)
    store.reset()
  }

  const handleAcceptAi = async (html: string) => {
    if (!store.assessmentId) return
    await api.acceptAiUpdate(store.assessmentId, store.selectedSectionIndex, html)
    store.updateSectionHtml(store.selectedSectionIndex, html)
    store.clearAiProposal(store.selectedSectionIndex)
  }

  const isModified = section.html !== section.original_html
  const canReset = isModified || section.status !== 'pending'

  return (
    <div className="flex h-full">
      {/* Left sidebar: section selector */}
      <div className="w-64 border-r border-gray-200 bg-white">
        <SectionSelector
          sections={store.sections}
          selectedIndex={store.selectedSectionIndex}
          onSelect={(idx) => store.setSelectedSection(idx)}
          onApproveAll={handleApproveAll}
          onFinalize={handleFinalize}
          onDiscard={handleDiscard}
        />
      </div>

      {/* Right panel: section content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* Section header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-800">{section.title}</h3>
            {section.status === 'approved' ? (
              <span className="inline-block px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full">
                Approved
              </span>
            ) : isModified ? (
              <span className="inline-block px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-800 rounded-full">
                Modified
              </span>
            ) : (
              <span className="inline-block px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full">
                Pending
              </span>
            )}
          </div>
          <div className="flex gap-2">
            {/* Prev/Next */}
            <button
              onClick={() => store.setSelectedSection(store.selectedSectionIndex - 1)}
              disabled={store.selectedSectionIndex === 0}
              className="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Prev
            </button>
            <button
              onClick={() => store.setSelectedSection(store.selectedSectionIndex + 1)}
              disabled={store.selectedSectionIndex >= store.sections.length - 1}
              className="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>

        {/* Preview */}
        <ReportPreview html={section.html} headHtml={store.headHtml} height={400} />

        {/* Approve / Reset */}
        <div className="flex gap-2 my-4">
          <button
            onClick={handleApprove}
            disabled={section.status === 'approved'}
            className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {section.status === 'approved' ? 'Already Approved' : 'Approve Section'}
          </button>
          <button
            onClick={handleReset}
            disabled={!canReset}
            className="px-4 py-2 text-sm bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Reset to Original
          </button>
        </div>

        {/* Tabs: Edit / AI Update */}
        <div className="border-b border-gray-200 mb-4">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveTab('edit')}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'edit'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Edit
            </button>
            <button
              onClick={() => setActiveTab('ai')}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'ai'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              AI Update
            </button>
          </div>
        </div>

        {activeTab === 'edit' && (
          <SectionEditor
            html={section.html}
            onApply={handleApplyEdit}
          />
        )}

        {activeTab === 'ai' && store.assessmentId && (
          <AiUpdatePanel
            assessmentId={store.assessmentId}
            sectionIdx={store.selectedSectionIndex}
            headHtml={store.headHtml}
            currentHtml={section.html}
            pendingProposal={store.pendingAiProposals[store.selectedSectionIndex]}
            onAccept={handleAcceptAi}
            onReject={() => store.clearAiProposal(store.selectedSectionIndex)}
          />
        )}
      </div>
    </div>
  )
}

// ────────────────────────────────────────────────────────────────
// Complete View
// ────────────────────────────────────────────────────────────────

function CompleteView() {
  const store = useAssessmentStore()

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
        <h2 className="text-lg font-bold text-green-800">Assessment Complete</h2>
        <p className="text-sm text-green-700">
          {store.reportName || 'Report'} has been finalized and archived.
        </p>
      </div>

      <div className="flex gap-3 mb-6">
        <button
          onClick={() => store.reset()}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 font-medium"
        >
          New Assessment
        </button>
      </div>
    </div>
  )
}
