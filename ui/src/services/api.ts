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
  user_id?: string | null;
  user_email?: string | null;
  user_name?: string | null;
  context?: ReviewRunContext | null;
}

export interface CognitiveComplexityProcedure {
  file_path: string;
  name: string;
  start_line: number;
  end_line: number;
  complexity: number;
  loc: number;
  avg_per_line: number;
}

export interface CognitiveComplexitySummary {
  total: number;
  total_loc: number;
  avg_per_line: number;
  procedures: CognitiveComplexityProcedure[];
}

export interface RunMetrics {
  cognitive_complexity?: CognitiveComplexitySummary;
}

export interface ReviewRunContext extends Record<string, unknown> {
  metrics?: RunMetrics | null;
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
  reviewer_comment?: string | null;
  evidence?: AIFindingEvidence[] | null;
  llm_raw_response?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface OpenWorldCandidateEvidence {
  file?: string | null;
  lines?: string | null;
  reason?: string | null;
}

export interface OpenWorldCandidate {
  id: string;
  review_run_id: string;
  title: string;
  section?: string | null;
  severity?: string | null;
  confidence?: number | null;
  description?: string | null;
  norm_text?: string | null;
  mapped_norm_id?: string | null;
  status: string;
  accepted_norm_id?: string | null;
  evidence?: OpenWorldCandidateEvidence[] | null;
  llm_raw_response?: Record<string, unknown> | null;
  created_at: string;
  mapped_norm_source_reference?: string | null;
  mapped_norm_source_excerpt?: string | null;
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

export interface LLMPlaygroundRequest {
  system_prompt: string;
  user_prompt: string;
  temperature: number;
  use_reasoning: boolean;
  model?: string;
}

export interface LLMPlaygroundResponse {
  model: string;
  response: string;
  api_base: string;
  endpoint: string;
  timeout_seconds: number;
  temperature: number;
  use_reasoning: boolean;
  model_override?: string | null;
  request_headers: Record<string, string>;
  request_payload: Record<string, unknown>;
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
  wallet_balance?: number | null;
  wallet_currency?: string | null;
  company_id?: string | null;
  company_name?: string | null;
  settings?: UserSettings | null;
}

export interface UserSettings {
  findings_view: 'separate' | 'combined';
  disable_patterns: boolean;
  use_all_norms: boolean;
  llm_provider: string;
  llm_model: string;
  open_world_use_chatgpt: boolean;
}

export interface UserSettingsUpdate {
  findings_view?: 'separate' | 'combined';
  disable_patterns?: boolean;
  use_all_norms?: boolean;
  llm_provider?: string;
  llm_model?: string;
  open_world_use_chatgpt?: boolean;
}

export interface NormCatalogEntry {
  norm_id: string;
  title?: string | null;
  section?: string | null;
  category?: string | null;
  norm_text?: string | null;
  scope?: string | null;
  detector_type?: string | null;
  check_type?: string | null;
  default_severity?: string | null;
  source_reference?: string | null;
  source_excerpt?: string | null;
  code_applicability?: boolean | null;
  is_active?: boolean | null;
  version?: number | null;
  priority?: number | null;
  rationale?: string | null;
  detection_hint?: string | null;
  exceptions?: string | null;
}

export interface NormRecord {
  id: string;
  norm_id: string;
  title: string;
  section: string;
  scope: string;
  detector_type: string;
  check_type: string;
  default_severity: string;
  norm_text: string;
  code_applicability: boolean;
  is_active: boolean;
  version: number;
  source_reference?: string | null;
  source_excerpt?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Company {
  id: string;
  name: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AccessLogEntry {
  id: number;
  created_at: string;
  user_id?: string | null;
  user_email?: string | null;
  ip_address: string;
  country_code?: string | null;
  method: string;
  path: string;
  status_code: number;
  duration_ms: number;
  user_agent?: string | null;
  block_reason?: string | null;
}

export interface CaddyAccessLogEntry {
  id: number;
  created_at: string;
  host?: string | null;
  method?: string | null;
  uri?: string | null;
  status_code?: number | null;
  duration_ms?: number | null;
  size_bytes?: number | null;
  remote_ip?: string | null;
  user_agent?: string | null;
  referer?: string | null;
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

export interface RawSourceEntry {
  path: string;
  size: number;
}

export async function fetchRuns(params?: { skip?: number; limit?: number; user_id?: string }) {
  const { data } = await client.get<ReviewRun[]>('/review-runs', { params });
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

export async function rerunReviewRun(id: string) {
  const { data } = await client.post<ReviewRun>(`/review-runs/${id}/rerun`);
  return data;
}

export async function deleteReviewRun(id: string) {
  await client.delete(`/review-runs/${id}`);
}

export async function forceFailReviewRun(id: string) {
  const { data } = await client.post<ReviewRun>(`/admin/review-runs/${id}/force-fail`);
  return data;
}

export async function requeueReviewRun(id: string) {
  const { data } = await client.post<ReviewRun>(`/admin/review-runs/${id}/requeue`);
  return data;
}

export interface FindingListResponse {
  total: number;
  items: Finding[];
}

export interface AIFindingListResponse {
  total: number;
  items: AIFinding[];
}

export interface OpenWorldCandidateListResponse {
  total: number;
  items: OpenWorldCandidate[];
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

export async function fetchOpenWorldCandidates(runId: string) {
  const { data } = await client.get<OpenWorldCandidateListResponse>(`/open-world-candidates`, {
    params: { review_run_id: runId },
  });
  return data;
}

export async function acceptOpenWorldCandidate(id: string) {
  const { data } = await client.post<OpenWorldCandidate>(`/open-world-candidates/${id}/accept`);
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

export async function startRunEvaluation(runId: string, selectionRuns: number) {
  const { data } = await client.post<ReviewRun>(`/review-runs/${runId}/evaluation`, {
    selection_runs: selectionRuns,
  });
  return data;
}

export async function fetchRunEvaluation(runId: string) {
  const { data } = await client.get<{
    evaluation_run_id: string | null;
    report: Record<string, unknown> | null;
    status: string | null;
  }>(`/review-runs/${runId}/evaluation`);
  return data;
}

export async function fetchRawSourcesIndex(runId: string) {
  const { data } = await client.get<RawSourceEntry[]>(`/review-runs/${runId}/sources-raw`);
  return data;
}

export async function fetchRawSourceContent(runId: string, path: string) {
  const { data } = await client.get<{ path: string; content: string }>(
    `/review-runs/${runId}/sources-raw/file`,
    { params: { path } },
  );
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

export async function updateUserSettings(payload: UserSettingsUpdate) {
  const { data } = await client.patch<UserProfile>('/users/me/settings', payload);
  return data;
}

export interface ChangelogResponse {
  content: string;
  updated_at: string;
}

export async function fetchChangelog() {
  const { data } = await client.get<ChangelogResponse>('/changelog');
  return data;
}

export async function fetchUsers(params?: {
  limit?: number;
  offset?: number;
  email?: string;
  status?: string;
  role?: string;
}) {
  const { data } = await client.get<UserProfile[]>('/users', { params });
  return data;
}

export async function updateUserStatus(userId: string, status: string) {
  const { data } = await client.patch<UserProfile>(`/users/${userId}/status`, { status });
  return data;
}

export async function updateUserRole(userId: string, role: string) {
  const { data } = await client.patch<UserProfile>(`/users/${userId}/role`, { role });
  return data;
}

export async function updateUserCompany(userId: string, companyId: string | null) {
  const { data } = await client.patch<UserProfile>(`/users/${userId}/company`, {
    company_id: companyId,
  });
  return data;
}

export async function fetchCompanies(params?: { limit?: number; offset?: number; name?: string }) {
  const { data } = await client.get<Company[]>('/companies', { params });
  return data;
}

export async function createCompany(payload: { name: string }) {
  const { data } = await client.post<Company>('/companies', payload);
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

export async function fetchNormCatalog(params: {
  source: 'static' | 'llm';
  query?: string;
  limit?: number;
}) {
  const { data } = await client.get<NormCatalogEntry[]>('/norms/catalog', { params });
  return data;
}

export async function fetchNorms(params?: { skip?: number; limit?: number }) {
  const { data } = await client.get<NormRecord[]>('/norms', { params });
  return data;
}

export async function createNorm(payload: Omit<NormRecord, 'id' | 'created_at' | 'updated_at'>) {
  const { data } = await client.post<NormRecord>('/norms', payload);
  return data;
}

export async function fetchCustomNorms() {
  const { data } = await client.get<NormCatalogEntry[]>('/norms/custom');
  return data;
}

export async function deleteCustomNorm(normId: string) {
  await client.delete(`/norms/custom/${normId}`);
}

// Suggested norms (teacher)
export interface SuggestedNormCreatePayload {
  section: string;
  severity: 'critical' | 'major' | 'minor' | 'info';
  text: string;
}

export interface SuggestedNorm {
  id: string;
  author_id: string;
  section: string;
  severity: string;
  text_raw: string;
  status: string;
  duplicate_of?: string[] | null;
  duplicate_titles?: Record<string, string | null> | null;
  generated_norm_id?: string | null;
  generated_title?: string | null;
  generated_section?: string | null;
  generated_scope?: string | null;
  generated_detector_type?: string | null;
  generated_check_type?: string | null;
  generated_severity?: string | null;
  generated_version?: number | null;
  generated_text?: string | null;
  created_at: string;
  updated_at: string;
  vote_score: number;
  user_vote: number | null;
}

export interface SuggestedNormListResponse {
  items: SuggestedNorm[];
  total: number;
}

export interface SuggestedNormAcceptPayload {
  norm_id?: string;
  title?: string;
  section?: string;
  scope?: string;
  norm_text?: string;
}

export async function fetchSuggestedNormSections() {
  const { data } = await client.get<string[]>('/suggested-norms/sections');
  return data;
}

export async function createSuggestedNorm(payload: SuggestedNormCreatePayload) {
  const { data } = await client.post<SuggestedNorm>('/suggested-norms', payload);
  return data;
}

export async function fetchSuggestedNorms(params?: { status?: string; limit?: number; offset?: number }) {
  const { data } = await client.get<SuggestedNormListResponse>('/suggested-norms', { params });
  return data;
}

export async function voteSuggestedNorm(normId: string, vote: 1 | -1) {
  await client.post(`/suggested-norms/${normId}/vote`, { vote });
}

export async function deleteSuggestedNorm(normId: string) {
  await client.delete(`/suggested-norms/${normId}`);
}

export async function acceptSuggestedNorm(normId: string, payload?: SuggestedNormAcceptPayload) {
  const { data } = await client.post<SuggestedNorm>(`/suggested-norms/${normId}/accept`, payload);
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
  captcha_token?: string;
  website?: string;
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

export async function fetchAccessLogs(params?: {
  limit?: number;
  ip?: string;
  user_id?: string;
  path?: string;
}) {
  const { data } = await client.get<AccessLogEntry[]>('/admin/access-logs', { params });
  return data;
}

export async function fetchCaddyLogs(params?: {
  limit?: number;
  host?: string;
  ip?: string;
  status?: number;
  path?: string;
}) {
  const { data } = await client.get<CaddyAccessLogEntry[]>('/admin/caddy-logs', { params });
  return data;
}

export async function runLLMPlayground(payload: LLMPlaygroundRequest) {
  const { data } = await client.post<LLMPlaygroundResponse>('/admin/llm/playground', payload);
  return data;
}

export async function updateAIFindingStatus(
  id: string,
  status: AIFindingStatus,
  reviewer_comment?: string | null,
) {
  const { data } = await client.patch<AIFinding>(`/ai-findings/${id}`, {
    status,
    reviewer_comment,
  });
  return data;
}
