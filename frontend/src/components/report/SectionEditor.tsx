import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { Table } from '@tiptap/extension-table'
import { TableRow } from '@tiptap/extension-table-row'
import { TableCell } from '@tiptap/extension-table-cell'
import { TableHeader } from '@tiptap/extension-table-header'
import { useEffect, useState } from 'react'

interface Props {
  html: string
  onApply: (html: string) => void
}

export default function SectionEditor({ html, onApply }: Props) {
  const [hasChanges, setHasChanges] = useState(false)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
      }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
    ],
    content: html,
    onUpdate: () => {
      setHasChanges(true)
    },
  })

  // Reset editor content when section changes
  useEffect(() => {
    if (editor && html !== editor.getHTML()) {
      editor.commands.setContent(html)
      setHasChanges(false)
    }
  }, [html, editor])

  const handleApply = () => {
    if (editor) {
      onApply(editor.getHTML())
      setHasChanges(false)
    }
  }

  const handleDiscard = () => {
    if (editor) {
      editor.commands.setContent(html)
      setHasChanges(false)
    }
  }

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center gap-1 p-2 bg-gray-50 border border-gray-200 rounded-t-lg">
        <ToolbarButton
          onClick={() => editor?.chain().focus().toggleBold().run()}
          active={editor?.isActive('bold')}
          label="B"
          title="Bold"
        />
        <ToolbarButton
          onClick={() => editor?.chain().focus().toggleItalic().run()}
          active={editor?.isActive('italic')}
          label="I"
          title="Italic"
        />
        <span className="w-px h-5 bg-gray-300 mx-1" />
        <ToolbarButton
          onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
          active={editor?.isActive('heading', { level: 2 })}
          label="H2"
          title="Heading 2"
        />
        <ToolbarButton
          onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
          active={editor?.isActive('heading', { level: 3 })}
          label="H3"
          title="Heading 3"
        />
        <ToolbarButton
          onClick={() => editor?.chain().focus().toggleHeading({ level: 4 }).run()}
          active={editor?.isActive('heading', { level: 4 })}
          label="H4"
          title="Heading 4"
        />
        <span className="w-px h-5 bg-gray-300 mx-1" />
        <ToolbarButton
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
          active={editor?.isActive('bulletList')}
          label="UL"
          title="Bullet List"
        />
        <ToolbarButton
          onClick={() => editor?.chain().focus().toggleOrderedList().run()}
          active={editor?.isActive('orderedList')}
          label="OL"
          title="Ordered List"
        />
      </div>

      {/* Editor */}
      <div className="border border-t-0 border-gray-200 rounded-b-lg bg-white max-h-[400px] overflow-y-auto">
        <EditorContent editor={editor} />
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-3">
        <button
          onClick={handleApply}
          disabled={!hasChanges}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Apply Changes
        </button>
        <button
          onClick={handleDiscard}
          disabled={!hasChanges}
          className="px-4 py-2 text-sm bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Discard
        </button>
        {hasChanges && (
          <span className="text-sm text-amber-600 self-center">Unsaved changes</span>
        )}
      </div>
    </div>
  )
}

function ToolbarButton({ onClick, active, label, title }: {
  onClick: () => void
  active?: boolean
  label: string
  title: string
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`px-2 py-1 text-xs font-mono rounded transition-colors ${
        active
          ? 'bg-blue-100 text-blue-800'
          : 'text-gray-600 hover:bg-gray-200'
      }`}
    >
      {label}
    </button>
  )
}
