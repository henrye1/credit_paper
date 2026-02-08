import { useRef, useEffect } from 'react'

interface Props {
  html: string
  headHtml?: string
  height?: number
}

export default function ReportPreview({ html, headHtml = '', height = 500 }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    const iframe = iframeRef.current
    if (!iframe) return

    const doc = iframe.contentDocument
    if (!doc) return

    doc.open()
    doc.write(
      `<!DOCTYPE html><html><head>${headHtml}</head>` +
      `<body style="padding:20px;font-family:system-ui,sans-serif;">${html}</body></html>`
    )
    doc.close()
  }, [html, headHtml])

  return (
    <iframe
      ref={iframeRef}
      className="w-full border border-gray-200 rounded-lg bg-white"
      style={{ height }}
      title="Report Preview"
    />
  )
}
