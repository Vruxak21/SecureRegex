/**
 * Typed API client for the SecureRegex backend.
 * All fetch calls go through here so we never scatter base URLs across components.
 */

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

export interface ApiError {
  error: string
  message: string
  detail?: string
}

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

export const api = {
  health: () => get<HealthResponse>('/health'),
  info:   () => get<InfoResponse>('/api/v1/info'),
}
