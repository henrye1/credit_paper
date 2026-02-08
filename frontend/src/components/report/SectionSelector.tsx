import type { Section } from '../../types'

interface Props {
  sections: Section[]
  selectedIndex: number
  onSelect: (idx: number) => void
  onApproveAll: () => void
  onFinalize: () => void
  onDiscard: () => void
}

export default function SectionSelector({
  sections, selectedIndex, onSelect, onApproveAll, onFinalize, onDiscard,
}: Props) {
  const approvedCount = sections.filter(s => s.status === 'approved').length
  const allApproved = approvedCount === sections.length
  const remaining = sections.length - approvedCount

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-gray-200">
        <div className="text-sm font-medium text-gray-700 mb-1">
          {approvedCount} of {sections.length} approved
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all"
            style={{ width: `${(approvedCount / sections.length) * 100}%` }}
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {sections.map((section, idx) => {
          const isModified = section.html !== section.original_html
          const icon = section.status === 'approved' ? '\u2705' : isModified ? '\u270E' : '\u25CB'
          const isActive = idx === selectedIndex

          return (
            <button
              key={section.id}
              onClick={() => onSelect(idx)}
              className={`w-full text-left px-3 py-2 text-sm transition-colors flex items-start gap-2 ${
                isActive
                  ? 'bg-blue-50 text-blue-800 font-medium'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              <span className="flex-shrink-0 mt-0.5">{icon}</span>
              <span className="truncate">{section.title}</span>
            </button>
          )
        })}
      </div>

      <div className="p-3 border-t border-gray-200 space-y-2">
        <button
          onClick={onApproveAll}
          disabled={remaining === 0}
          className="w-full px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Approve All ({remaining})
        </button>
        <button
          onClick={onFinalize}
          disabled={!allApproved}
          className="w-full px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          Finalize Report
        </button>
        <button
          onClick={onDiscard}
          className="w-full px-3 py-1.5 text-xs text-red-600 hover:text-red-800 hover:bg-red-50 rounded"
        >
          Discard
        </button>
      </div>
    </div>
  )
}
