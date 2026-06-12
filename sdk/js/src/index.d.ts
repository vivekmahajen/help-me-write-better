// TypeScript declarations for the help-me-write-better SDK.
// Mirrors the OpenAPI contract at GET /v1/openapi.json.

export type ServiceFormat =
  | "markdown" | "html" | "plain" | "rich-text"
  | "email" | "report" | "doc" | "slide-outline";

export type Effort = "low" | "medium" | "high" | "max";

export interface ImproveRequest {
  text: string;
  services?: string | string[];
  format?: ServiceFormat;
  show_changes?: boolean;
  tone?: string;
  audience?: string;
  length?: string;
  reading_level?: string;
  language?: string;
  request?: string;
  model?: string;
  effort?: Effort;
}

export interface Tokens { input_tokens: number; output_tokens: number; }

export interface Quota {
  plan: string;
  premium_cap: number;
  premium_used: number;
  premium_remaining: number;
  period_start?: number;
}

export interface ImproveResponse {
  text: string;
  model: string;
  services: string[];
  usage: Tokens;
  quota: Quota;
}

export interface Suggestion {
  range: { start: number; end: number };
  type: "spelling" | "grammar" | "punctuation" | "style" | "capitalization";
  severity: "low" | "medium" | "high";
  message: string;
  replacements: string[];
}

export interface CheckResponse { suggestions: Suggestion[]; count: number; }

export interface PlagiarismResult {
  status: string;
  content_hash: string;
  overall_match_pct: number;
  sources: { url: string; title: string; match_pct: number; spans: unknown[] }[];
  scanned_words: number;
  credits_charged: number;
  cached: boolean;
  disclaimer: string;
}

export interface AiDetectionResult {
  status: string;
  band: "human" | "uncertain" | "likely_ai";
  score: number;
  confidence_note: string;
  per_section: { start: number; end: number; band: string; score: number }[];
  credits_charged: number;
  cached: boolean;
}

export interface ScanResponse {
  scan_id: string;
  status: "pending" | "complete" | "failed";
  plagiarism?: PlagiarismResult;
  ai_detection?: AiDetectionResult;
}

export interface CiteItem {
  input: string;
  csl_json: Record<string, unknown>;
  bibliography_entry?: string;
  in_text?: string;
  resolver: string;
  parsed_by: string;
  warnings: string[];
}

export interface CiteResponse { style: string; items: CiteItem[]; bibliography: string[]; }

export interface AnalyticsSummary {
  calls: number;
  words: number;
  suggestions: number;
  by_service: Record<string, number>;
  by_issue_type: Record<string, number>;
  by_day: Record<string, { calls: number; words: number }>;
  estimated_minutes_saved: number;
}

export interface AnalyticsResponse {
  window_days: number;
  summary: AnalyticsSummary;
  insights: {
    this_week: AnalyticsSummary;
    last_week: AnalyticsSummary;
    deltas: { calls: number; words: number; suggestions: number };
  };
}

export interface StyleGuide {
  tone?: string;
  formality?: string;
  banned_terms?: string[];
  preferred_terms?: Record<string, string>;
  formatting_rules?: string;
  notes?: string;
}

export interface Member { user_id: number; email: string; role: string; }

export interface Org {
  id: number;
  name: string;
  plan: string;
  seats: number;
  seats_used: number;
  role: string | null;
  members: Member[];
}

export interface Account { email: string; plan: string; }

export interface UsageReport {
  quota: Quota;
  summary: {
    calls: number;
    premium_calls: number;
    input_tokens: number;
    output_tokens: number;
  };
}

export interface HistoryEvent {
  id: number; ts: number; services: string; model: string;
  premium: number; input_tokens: number; output_tokens: number;
}

export type Preferences = Record<string, unknown>;

export interface DocumentSummary {
  id: number; title: string; created_at: number; updated_at: number; versions: number;
}

export interface Document extends DocumentSummary {
  content: string;
  latest_version_id: number | null;
}

export interface Version { id: number; content: string; created_at: number; }

export interface ErrorBody { error: string; code?: string; }

export class WriteBetterError extends Error {
  status: number;
  code?: string;
  body: ErrorBody;
  constructor(status: number, body: ErrorBody);
}

export interface ClientOptions {
  apiKey: string;
  baseUrl?: string;
  fetch?: typeof fetch;
}

export class WriteBetterClient {
  constructor(options: ClientOptions);
  improve(request: ImproveRequest): Promise<ImproveResponse>;
  listTemplates(category?: string): Promise<Record<string, unknown>[]>;
  useTemplate(template: string, fields: Record<string, unknown>, extra?: Record<string, unknown>): Promise<ImproveResponse & { template: string; variants: string[] }>;
  check(text: string, previous?: string): Promise<CheckResponse>;
  scan(text: string, modes?: ("plagiarism" | "ai_detection")[], minMatchPct?: number): Promise<ScanResponse>;
  getScan(scanId: string): Promise<ScanResponse>;
  fingerprint(text: string): Promise<Record<string, unknown>>;
  cite(inputs: string[], style?: "apa" | "mla" | "chicago", options?: Record<string, unknown>): Promise<CiteResponse>;
  listCitations(): Promise<unknown[]>;
  getAccount(): Promise<Account>;
  getUsage(): Promise<UsageReport>;
  getAnalytics(windowDays?: number): Promise<AnalyticsResponse>;
  getHistory(): Promise<HistoryEvent[]>;
  getPreferences(): Promise<Preferences>;
  setPreferences(prefs: Preferences): Promise<Preferences>;
  getTeam(): Promise<Org | null>;
  createTeam(name: string): Promise<Org>;
  listMembers(): Promise<Member[]>;
  addMember(email: string, role?: "admin" | "member"): Promise<Member>;
  removeMember(userId: number): Promise<boolean>;
  getStyleGuide(): Promise<StyleGuide>;
  setStyleGuide(guide: StyleGuide): Promise<StyleGuide>;
  getTeamAnalytics(): Promise<Record<string, unknown>>;
  listDocuments(): Promise<DocumentSummary[]>;
  createDocument(content: string, title?: string): Promise<Document>;
  getDocument(id: number): Promise<Document>;
  renameDocument(id: number, title: string): Promise<Document>;
  deleteDocument(id: number): Promise<boolean>;
  listVersions(id: number): Promise<Version[]>;
  addVersion(id: number, content: string): Promise<Document>;
}

export default WriteBetterClient;
