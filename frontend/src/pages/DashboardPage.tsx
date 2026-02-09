import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

interface Stats {
  inputFiles: number
  examples: number
  reports: number
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>({ inputFiles: 0, examples: 0, reports: 0 })

  useEffect(() => {
    Promise.all([
      fetch('/api/settings/directories').then(r => r.json()),
      fetch('/api/reports').then(r => r.json()),
      fetch('/api/examples').then(r => r.json()),
    ]).then(([dirs, reports, examples]) => {
      const inputDir = dirs.find((d: any) => d.label === 'Report Inputs')
      setStats({
        inputFiles: inputDir?.file_count || 0,
        examples: examples.length,
        reports: reports.length,
      })
    }).catch(() => {})
  }, [])

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Dashboard</h2>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard label="Input Files" value={stats.inputFiles} />
        <StatCard label="Learning Examples" value={stats.examples} />
        <StatCard label="Generated Reports" value={stats.reports} />
      </div>

      <h3 className="text-lg font-semibold text-gray-700 mb-4">Quick Actions</h3>
      <div className="grid grid-cols-3 gap-4">
        <ActionCard to="/quick-assessment" label="Quick Assessment" description="Upload files and generate a report" />
        <ActionCard to="/pipeline" label="Dev Pipeline" description="Run individual pipeline stages" />
        <ActionCard to="/prompts" label="Prompt Editor" description="Edit and version prompts" />
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-800">{value}</p>
    </div>
  )
}

function ActionCard({ to, label, description }: { to: string; label: string; description: string }) {
  return (
    <Link
      to={to}
      className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition-all"
    >
      <p className="font-medium text-gray-800">{label}</p>
      <p className="text-sm text-gray-500">{description}</p>
    </Link>
  )
}
