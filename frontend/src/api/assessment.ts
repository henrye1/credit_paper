import type { SectionsResponse, AssessmentStatus, AiUpdateResponse } from '../types'

const BASE = '/api/assessment'

export async function startAssessment(
  ratioFile: File,
  pdfFiles: File[],
  model: string,
  skipBizDesc: boolean,
  reportName: string,
  promptSet: string = ''
): Promise<{ assessment_id: string }> {
  const form = new FormData()
  form.append('ratio_file', ratioFile)
  pdfFiles.forEach(f => form.append('pdf_files', f))
  form.append('model', model)
  form.append('skip_biz_desc', String(skipBizDesc))
  form.append('report_name', reportName)
  form.append('prompt_set', promptSet)

  const res = await fetch(`${BASE}/start`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getStatus(id: string): Promise<AssessmentStatus> {
  const res = await fetch(`${BASE}/${id}/status`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getSections(id: string): Promise<SectionsResponse> {
  const res = await fetch(`${BASE}/${id}/sections`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function updateSection(id: string, idx: number, html: string) {
  const res = await fetch(`${BASE}/${id}/sections/${idx}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function approveSection(id: string, idx: number) {
  const res = await fetch(`${BASE}/${id}/sections/${idx}/approve`, { method: 'PUT' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function resetSection(id: string, idx: number) {
  const res = await fetch(`${BASE}/${id}/sections/${idx}/reset`, { method: 'PUT' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function aiUpdateSection(
  id: string,
  idx: number,
  instruction: string,
  includeContext: boolean,
  evidenceFiles: File[]
): Promise<AiUpdateResponse> {
  const form = new FormData()
  form.append('instruction', instruction)
  form.append('include_context', String(includeContext))
  evidenceFiles.forEach(f => form.append('evidence_files', f))

  const res = await fetch(`${BASE}/${id}/sections/${idx}/ai-update`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function acceptAiUpdate(id: string, idx: number, proposedHtml: string) {
  const res = await fetch(`${BASE}/${id}/sections/${idx}/accept-ai`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposed_html: proposedHtml }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function approveAllSections(id: string) {
  const res = await fetch(`${BASE}/${id}/approve-all`, { method: 'PUT' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function finalizeAssessment(id: string) {
  const res = await fetch(`${BASE}/${id}/finalize`, { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function discardAssessment(id: string) {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getPastAssessments() {
  const res = await fetch(`${BASE}/past`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getPastReport(name: string) {
  const res = await fetch(`${BASE}/past/${name}/report`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
