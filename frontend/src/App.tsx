import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import QuickAssessmentPage from './pages/QuickAssessmentPage'
import PipelinePage from './pages/PipelinePage'
import PromptEditorPage from './pages/PromptEditorPage'
import ExamplesPage from './pages/ExamplesPage'
import VersionHistoryPage from './pages/VersionHistoryPage'
import SettingsPage from './pages/SettingsPage'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/quick-assessment" element={<QuickAssessmentPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/prompts" element={<PromptEditorPage />} />
            <Route path="/examples" element={<ExamplesPage />} />
            <Route path="/history" element={<VersionHistoryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
