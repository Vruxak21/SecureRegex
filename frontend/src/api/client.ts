/**
 * Typed API client for the SecureRegex backend.
 * All fetch calls go through here so we never scatter base URLs across components.
 */

import type { AnalyzeResponse, TestResponse, ApiError } from '../types/api'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

export interface HealthResponse {
  status: string
  version: string
  app: string
}

export interface ApiLimits {
  max_regex_length: number
  max_input_length: number
  max_nfa_states: number
  max_dfa_states: number
  max_computation_steps: number
}

export interface InfoResponse {
  name: string
  version: string
  limits: ApiLimits
}

// ── Generic HTTP helpers ──────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) {
    const err: ApiError = await res.json().catch(() => ({
      error: 'NETWORK_ERROR',
      message: `HTTP ${res.status} ${res.statusText}`,
    }))
    throw err
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err: ApiError = await res.json().catch(() => ({
      error: 'NETWORK_ERROR',
      message: `HTTP ${res.status} ${res.statusText}`,
    }))
    throw err
  }
  return res.json() as Promise<T>
}

// ── Public API object ─────────────────────────────────────────────────────────

export const api = {
  health:  () => get<HealthResponse>('/health'),
  info:    () => get<InfoResponse>('/api/v1/info'),
  analyze: (regex: string) =>
    post<AnalyzeResponse>('/api/v1/analyze', { regex }),
  test:    (regex: string, input: string) =>
    post<TestResponse>('/api/v1/test', { regex, input }),
}

/** Parse an unknown thrown value into a user-readable error message. */
export function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const e = err as ApiError
    if (e.message) {
      let msg = e.message
      if (e.position) msg += ` (column ${e.position.column})`
      if (e.char)     msg += ` — offending character: '${e.char}'`
      return msg
    }
  }
  if (err instanceof Error) return err.message
  return String(err)
}
