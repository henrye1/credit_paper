import { useRef } from 'react'

interface Props {
  label: string
  accept: string
  multiple?: boolean
  files: File[]
  onChange: (files: File[]) => void
  required?: boolean
}

export default function FileUploader({ label, accept, multiple, files, onChange, required }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <div
        onClick={() => inputRef.current?.click()}
        className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(e) => onChange(Array.from(e.target.files || []))}
          className="hidden"
        />
        {files.length === 0 ? (
          <p className="text-sm text-gray-500">Click to select files</p>
        ) : (
          <div className="space-y-1">
            {files.map((f, i) => (
              <p key={i} className="text-sm text-gray-700">{f.name} ({(f.size / 1024).toFixed(0)} KB)</p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
