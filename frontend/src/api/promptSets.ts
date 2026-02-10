import type { PromptSet } from '../types'

const BASE = '/api/prompt-sets'

export async function listPromptSets(): Promise<PromptSet[]> {
  const res = await fetch(BASE)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function createPromptSet(
  slug: string, displayName: string, description: string = ''
): Promise<PromptSet> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug, display_name: displayName, description }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function clonePromptSet(
  sourceSlug: string, newSlug: string, newDisplayName: string, newDescription: string = ''
): Promise<PromptSet> {
  const res = await fetch(`${BASE}/${sourceSlug}/clone`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      new_slug: newSlug,
      new_display_name: newDisplayName,
      new_description: newDescription,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function updatePromptSet(
  slug: string, displayName?: string, description?: string
): Promise<PromptSet> {
  const res = await fetch(`${BASE}/${slug}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName, description }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function deletePromptSet(slug: string): Promise<void> {
  const res = await fetch(`${BASE}/${slug}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
}

export async function setDefaultPromptSet(slug: string): Promise<void> {
  const res = await fetch(`${BASE}/default`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug }),
  })
  if (!res.ok) throw new Error(await res.text())
}
