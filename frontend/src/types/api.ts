/**
 * TypeScript types mirroring the backend Pydantic response models exactly.
 */

// ── Lexer ─────────────────────────────────────────────────────────────────────

export interface Token {
  type: string
  value: string
  column: number
}

// ── AST ───────────────────────────────────────────────────────────────────────

export type ASTNode = Record<string, unknown>

// ── Automata ──────────────────────────────────────────────────────────────────

export interface AutomataTransition {
  from: number
  symbol: string
  to: number
}

export interface Automaton {
  states: number[]
  alphabet: string[]
  transitions: AutomataTransition[]
  start: number
  accepting: number[]
}

// ── Semantic ──────────────────────────────────────────────────────────────────

export interface DiagnosticLocation {
  line: number
  column: number
}

export interface Diagnostic {
  severity: 'ERROR' | 'WARNING' | 'INFO'
  code: string
  message: string
  location?: DiagnosticLocation | null
}

// ── Security ──────────────────────────────────────────────────────────────────

export interface SecurityLocation {
  start: number
  end: number
}

export interface SecurityFinding {
  rule_id: string
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW'
  title: string
  reason: string
  explanation: string
  recommendation: string
  location: SecurityLocation | null
}

export interface SecurityReport {
  overall_risk: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'
  findings: SecurityFinding[]
  caveat: string
}

// ── Statistics ────────────────────────────────────────────────────────────────

export interface PipelineStats {
  regex_length: number
  token_count: number
  ast_node_count: number
  nfa_states: number
  nfa_transitions: number
  dfa_states: number
  dfa_transitions: number
  minimized_dfa_states: number
  dfa_reduction_pct: number
  overall_security_risk: string
}

// ── API responses ─────────────────────────────────────────────────────────────

export interface AnalyzeResponse {
  success: boolean
  tokens: Token[]
  ast: ASTNode
  nfa: Automaton
  dfa: Automaton
  minimized_dfa: Automaton
  diagnostics: Diagnostic[]
  security: SecurityReport
  stats: PipelineStats
}

export interface TestResponse {
  matched: boolean
  path: number[]
}

export interface ApiError {
  error: string
  message: string
  position?: { line: number; column: number } | null
  char?: string | null
  detail?: string | null
}
