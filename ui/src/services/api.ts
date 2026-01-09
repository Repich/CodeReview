import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export const client = axios.create({
  baseURL: API_BASE,
});

const TOKEN_STORAGE_KEY = 'codereview_token';

const isBrowser = typeof window !== 'undefined';

export function getStoredAuthToken(): string | null {
  if (!isBrowser) return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setAuthToken(token: string | null) {
  if (!isBrowser) return;
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    delete client.defaults.headers.common['Authorization'];
  }
}

const initialToken = getStoredAuthToken();
if (initialToken) {
  client.defaults.headers.common['Authorization'] = `Bearer ${initialToken}`;
}

export interface ReviewRun {
  id: string;
  project_id?: string | null;
  status: string;
  queued_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  cost_points?: number | null;
  llm_prompt_version?: string | null;
}

export interface SourceUnitPayload {
  path: string;
  name: string;
  content: string;
  module_type: string;
}

export interface CreateReviewRunPayload {
  project_id?: string;
  external_ref?: string;
  sources: SourceUnitPayload[];
}

export interface Finding {
  id: string;
  norm_id: string;
  detector_id: string;
  severity: string;
  norm_title?: string | null;
  norm_text?: string | null;
  norm_section?: string | null;
  norm_source_reference?: string | null;
  norm_source_excerpt?: string | null;
  message: string;
  code_snippet?: string | null;
  file_path?: string | null;
  line_start?: number | null;
  line_end?: number | null;
  context?: Record<string, unknown> | null;
}

export type AIFindingStatus = 'suggested' | 'pending' | 'confirmed' | 'rejected';

export interface AIFindingEvidence {
  file?: string | null;
  lines?: string | null;
  reason?: string | null;
}

export interface AIFinding {
  id: string;
  review_run_id: string;
  status: AIFindingStatus;
  norm_id?: string | null;
  section?: string | null;
  category?: string | null;
  severity?: string | null;
  norm_text: string;
  source_reference?: string | null;
  norm_source_reference?: string | null;
  norm_source_excerpt?: string | null;
  evidence?: AIFindingEvidence[] | null;
  llm_raw_response?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface LLMLogEntry {
  io_log_id: string;
  created_at: string;
  artifact_type: string;
  data: {
    prompt: string;
    response: string;
    context_files: string[];
    source_paths: string[];
    static_findings: Record<string, unknown>[];
    created_at: string;
    prompt_version?: string | null;
    unit_id?: string | null;
    unit_name?: string | null;
  };
}

export interface AuditLog {
  id: string;
  review_run_id?: string | null;
  event_type: string;
  actor?: string | null;
  payload?: Record<string, unknown> | null;
  created_at: string;
}

export interface FeedbackEntry {
  id: string;
  review_run_id: string;
  finding_id: string;
  reviewer: string;
  verdict: string;
  comment?: string | null;
  created_at: string;
}

export interface FeedbackListResponse {
  total: number;
  items: FeedbackEntry[];
}

export interface UserProfile {
  id: string;
  email: string;
  name?: string | null;
  status: string;
  role: string;
  created_at: string;
}

export interface WalletInfo {
  id: string;
  balance: number;
  currency: string;
}

export interface WalletTransaction {
  id: string;
  wallet_id: string;
  txn_type: string;
  source: string;
  amount: number;
  context?: Record<string, unknown> | null;
  created_at: string;
}

export interface IOLogEntry {
  id: string;
  review_run_id: string;
  direction: string;
  artifact_type: string;
  storage_path: string;
  checksum?: string | null;
  size_bytes?: number | null;
  created_at: string;
}

export interface RunSource {
  path: string;
  name?: string | null;
  module_type?: string | null;
  content: string;
  change_ranges?: { start: number; end: number }[] | null;
}

export async function fetchRuns() {
  const { data } = await client.get<ReviewRun[]>('/review-runs');
  return data;
}

export async function fetchRun(id: string) {
  const { data } = await client.get<ReviewRun>(`/review-runs/${id}`);
  return data;
}

export async function createReviewRun(payload: CreateReviewRunPayload) {
  const { data } = await client.post<ReviewRun>('/review-runs', payload);
  return data;
}

export async function deleteReviewRun(id: string) {
  await client.delete(`/review-runs/${id}`);
}

export interface FindingListResponse {
  total: number;
  items: Finding[];
}

export interface AIFindingListResponse {
  total: number;
  items: AIFinding[];
}

export async function fetchFindings(runId: string) {
  const { data } = await client.get<FindingListResponse>(`/findings`, {
    params: { review_run_id: runId },
  });
  return data;
}

export async function fetchAIFindings(runId: string) {
  const { data } = await client.get<AIFindingListResponse>(`/ai-findings`, {
    params: { review_run_id: runId },
  });
  return data;
}

export async function fetchLLMLogs(runId: string) {
  const { data } = await client.get<LLMLogEntry[]>(`/review-runs/${runId}/llm/logs`);
  return data;
}

export async function fetchAuditLogs(runId: string) {
  const { data } = await client.get<AuditLog[]>(`/audit/logs`, {
    params: { review_run_id: runId },
  });
  return data;
}

export async function fetchFeedback(runId: string) {
  const { data } = await client.get<FeedbackListResponse>(`/feedback`, {
    params: { review_run_id: runId },
  });
  return data;
}

export async function fetchIOLogs(runId: string) {
  const { data } = await client.get<IOLogEntry[]>(`/audit/io`, {
    params: { review_run_id: runId },
  });
  return data;
}

export async function fetchRunSources(runId: string) {
  const { data } = await client.get<RunSource[]>(`/review-runs/${runId}/sources`);
  return data;
}

export async function downloadFindingsJsonl(runId: string) {
  const { data } = await client.get<Blob>(`/findings/export/${runId}.jsonl`, {
    responseType: 'blob',
  });
  return data;
}

export async function fetchCurrentUser() {
  const { data } = await client.get<UserProfile>('/users/me');
  return data;
}

export async function fetchWallet() {
  const { data } = await client.get<WalletInfo>('/wallets/me');
  return data;
}

export async function fetchWalletTransactions() {
  const { data } = await client.get<WalletTransaction[]>('/wallets/transactions');
  return data;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  name?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export async function login(payload: LoginPayload) {
  const { data } = await client.post<TokenResponse>('/auth/login', payload);
  return data;
}

export async function register(payload: RegisterPayload) {
  const { data } = await client.post<TokenResponse>('/auth/register', payload);
  return data;
}

export interface WalletAdjustPayload {
  user_id?: string;
  user_email?: string;
  amount: number;
  reason: string;
}

export async function adjustWalletBalance(payload: WalletAdjustPayload) {
  const { data } = await client.post<WalletTransaction>('/wallets/adjust', payload);
  return data;
}

export async function updateAIFindingStatus(id: string, status: AIFindingStatus) {
  const { data } = await client.patch<AIFinding>(`/ai-findings/${id}`, { status });
  return data;
}
