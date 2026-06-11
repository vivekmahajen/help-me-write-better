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
  getAccount(): Promise<Account>;
  getUsage(): Promise<UsageReport>;
  getHistory(): Promise<HistoryEvent[]>;
  getPreferences(): Promise<Preferences>;
  setPreferences(prefs: Preferences): Promise<Preferences>;
  listDocuments(): Promise<DocumentSummary[]>;
  createDocument(content: string, title?: string): Promise<Document>;
  getDocument(id: number): Promise<Document>;
  renameDocument(id: number, title: string): Promise<Document>;
  deleteDocument(id: number): Promise<boolean>;
  listVersions(id: number): Promise<Version[]>;
  addVersion(id: number, content: string): Promise<Document>;
}

export default WriteBetterClient;
