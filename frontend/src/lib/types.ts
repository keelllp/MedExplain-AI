// TypeScript types mirroring the backend API contract (docs/04-api-spec.md).

export type LLMMode = "cloud" | "offline";
export type ReportStatus = "uploaded" | "processing" | "analyzed" | "failed";
export type Severity = "normal" | "mild" | "moderate" | "severe";
export type Direction = "low" | "high" | "normal";

export interface UserOut {
  id: number;
  email: string;
  full_name: string | null;
  llm_mode: LLMMode;
  gemini_consent: boolean;
  gemini_consented_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserOut;
}

export interface ReportSummary {
  id: number;
  title: string;
  report_type: string;
  status: ReportStatus;
  progress: number;
  error_code: string | null;
  ocr_confidence: number | null;
  uploaded_at: string;
  analyzed_at: string | null;
}

export interface Citation {
  n: number;
  doc_title: string;
  section: string | null;
  source_path: string | null;
}

export interface Biomarker {
  id: number;
  test_name: string;
  canonical_name: string | null;
  value: number | null;
  value_text: string | null;
  unit: string | null;
  canonical_unit: string | null;
  reference_low: number | null;
  reference_high: number | null;
  reference_range_text: string | null;
  captured_at: string | null;
}

export interface Finding {
  id: number;
  biomarker_id: number;
  status: string;
  severity: Severity;
  direction: Direction;
  rule_id: string | null;
  explanation: string | null;
  citations: Citation[];
}

export interface Summary {
  id: number;
  summary_text: string;
  generation_mode: string;
  model_used: string;
  generated_at: string;
}

export interface DoctorQuestion {
  id: number;
  question_text: string;
  category: string;
  ordering: number;
}

export interface ReportDetail extends ReportSummary {
  biomarkers: Biomarker[];
  findings: Finding[];
  summary: Summary | null;
  doctor_questions: DoctorQuestion[];
  disclaimer: string;
}

export interface ReportUploadResponse {
  report_id: number;
  status: ReportStatus;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
}

export interface AnalyzeAccepted {
  report_id: number;
  status: ReportStatus;
  progress: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// --- chat (Phase 7) ---
export type GenerationMode = "gemini" | "ollama" | "offline_template";

export interface ChatCitation {
  doc: string;
  chunk_id: string;
  score: number;
}

export interface ChatSession {
  id: number;
  report_id: number | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  created_at: string;
}

export interface ChatResponse {
  session_id: number;
  message_id: number;
  answer: string;
  citations: ChatCitation[];
  refused: boolean;
  generation_mode: GenerationMode;
  disclaimer: string;
}

// --- trends (Phase 8) ---
export type TrendLabel = "improving" | "worsening" | "stable" | "insufficient_data";

export interface TrendPoint {
  report_id: number;
  point_time: string;
  value: number;
  unit: string | null;
  canonical_unit: string | null;
  reference_low: number | null;
  reference_high: number | null;
  severity: Severity | null;
  direction: Direction | null;
}

export interface TrendResponse {
  biomarker: string;
  display: string;
  points: TrendPoint[];
  trend: TrendLabel;
  disclaimer: string;
}

export interface TrendableBiomarker {
  canonical_name: string;
  display: string;
  count: number;
  latest_point_time: string;
}
