import { create } from 'zustand'
import type { Section } from '../types'

interface AssessmentState {
  assessmentId: string | null
  phase: 'upload' | 'generating' | 'review' | 'complete'
  headHtml: string
  sections: Section[]
  selectedSectionIndex: number
  pendingAiProposals: Record<number, string>
  modelChoice: string
  reportName: string | null
  promptSet: string

  setAssessmentId: (id: string | null) => void
  setPhase: (phase: AssessmentState['phase']) => void
  setSections: (headHtml: string, sections: Section[]) => void
  setSelectedSection: (idx: number) => void
  updateSectionHtml: (idx: number, html: string) => void
  updateSectionStatus: (idx: number, status: 'pending' | 'approved') => void
  setAiProposal: (idx: number, html: string) => void
  clearAiProposal: (idx: number) => void
  setModelChoice: (model: string) => void
  setReportName: (name: string | null) => void
  setPromptSet: (slug: string) => void
  reset: () => void
  advanceToNextUnapproved: () => void
}

const initialState = {
  assessmentId: null as string | null,
  phase: 'upload' as const,
  headHtml: '',
  sections: [] as Section[],
  selectedSectionIndex: 0,
  pendingAiProposals: {} as Record<number, string>,
  modelChoice: 'gemini-2.5-flash',
  reportName: null as string | null,
  promptSet: '',
}

export const useAssessmentStore = create<AssessmentState>((set, get) => ({
  ...initialState,

  setAssessmentId: (id) => set({ assessmentId: id }),
  setPhase: (phase) => set({ phase }),
  setSections: (headHtml, sections) => set({ headHtml, sections }),
  setSelectedSection: (idx) => set({ selectedSectionIndex: idx }),

  updateSectionHtml: (idx, html) => set(state => {
    const sections = [...state.sections]
    sections[idx] = { ...sections[idx], html }
    if (sections[idx].status === 'approved') {
      sections[idx] = { ...sections[idx], status: 'pending' }
    }
    return { sections }
  }),

  updateSectionStatus: (idx, status) => set(state => {
    const sections = [...state.sections]
    sections[idx] = { ...sections[idx], status }
    return { sections }
  }),

  setAiProposal: (idx, html) => set(state => ({
    pendingAiProposals: { ...state.pendingAiProposals, [idx]: html },
  })),

  clearAiProposal: (idx) => set(state => {
    const proposals = { ...state.pendingAiProposals }
    delete proposals[idx]
    return { pendingAiProposals: proposals }
  }),

  setModelChoice: (model) => set({ modelChoice: model }),
  setReportName: (name) => set({ reportName: name }),
  setPromptSet: (slug) => set({ promptSet: slug }),

  reset: () => set(initialState),

  advanceToNextUnapproved: () => {
    const { sections, selectedSectionIndex } = get()
    for (let offset = 1; offset <= sections.length; offset++) {
      const candidate = (selectedSectionIndex + offset) % sections.length
      if (sections[candidate].status !== 'approved') {
        set({ selectedSectionIndex: candidate })
        return
      }
    }
  },
}))
