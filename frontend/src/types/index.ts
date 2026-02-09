export interface Section {
  id: string
  title: string
  html: string
  original_html: string
  status: 'pending' | 'approved'
}

export interface SectionsResponse {
  head_html: string
  sections: Section[]
}

export interface AssessmentStatus {
  assessment_id: string
  phase: 'generating' | 'review' | 'complete' | 'error'
  stage?: string
  message?: string
  section_count?: number
  approved_count?: number
}

export interface AiUpdateResponse {
  success: boolean
  proposed_html: string
  message: string
}

export interface PastAssessment {
  name: string
  report_name: string | null
  input_files: string[]
  has_state: boolean
}

export interface PromptListItem {
  name: string
  label: string
  section_count: number
}
