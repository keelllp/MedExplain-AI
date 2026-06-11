// Typed API client: base URL, JWT bearer injection, consistent error handling.

import type {
  AnalyzeAccepted,
  ChatMessage,
  ChatResponse,
  ChatSession,
  Page,
  ReportDetail,
  ReportSummary,
  ReportUploadResponse,
  TokenOut,
  TrendableBiomarker,
  TrendResponse,
  UserOut,
} from "@/lib/types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "medexplain_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  if (typeof window !== "undefined") window.localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  if (typeof window !== "undefined") window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  // Skip ngrok's free-tier browser interstitial so the API returns JSON, not HTML.
  const headers: Record<string, string> = { "ngrok-skip-browser-warning": "true" };
  if (opts.auth !== false) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form; // browser sets multipart Content-Type + boundary
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { method: opts.method ?? "GET", headers, body });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server. Is the backend running?");
  }

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // An authed request returning 401 means the token is missing/expired/invalid: clear it
    // and notify the app so it bounces the user to /login (instead of dead-looping).
    if (res.status === 401 && opts.auth !== false && getToken()) {
      clearToken();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("medexplain:unauthorized"));
      }
    }
    const err = (data?.error ?? {}) as { code?: string; message?: string; details?: unknown };
    throw new ApiError(res.status, err.code ?? "error", err.message ?? res.statusText, err.details);
  }
  return data as T;
}

// --- auth / account ---
export const register = (email: string, password: string, full_name?: string | null) =>
  request<UserOut>("/auth/register", { method: "POST", body: { email, password, full_name }, auth: false });
export const login = (email: string, password: string) =>
  request<TokenOut>("/auth/login", { method: "POST", body: { email, password }, auth: false });
export const me = () => request<UserOut>("/auth/me");
export const updateProfile = (full_name: string) =>
  request<UserOut>("/users/me", { method: "PATCH", body: { full_name } });
export const updateSettings = (llm_mode: string) =>
  request<UserOut>("/users/me/settings", { method: "PATCH", body: { llm_mode } });
export const changePassword = (current_password: string, new_password: string) =>
  request<{ message: string }>("/auth/change-password", {
    method: "POST",
    body: { current_password, new_password },
  });
export const deleteAccount = () => request<{ message: string }>("/users/me", { method: "DELETE" });

// --- reports ---
export const uploadReport = (form: FormData) =>
  request<ReportUploadResponse>("/reports/upload", { method: "POST", form });
export const analyzeReport = (report_id: number) =>
  request<AnalyzeAccepted>("/reports/analyze", { method: "POST", body: { report_id } });
export const listReports = (limit = 20, offset = 0) =>
  request<Page<ReportSummary>>(`/reports?limit=${limit}&offset=${offset}`);
export const getReport = (id: number) => request<ReportDetail>(`/reports/${id}`);
export const deleteReport = (id: number) =>
  request<{ message: string }>(`/reports/${id}`, { method: "DELETE" });

// --- chat ---
export const postChat = (body: { message: string; session_id?: number; report_id?: number }) =>
  request<ChatResponse>("/chat", { method: "POST", body });
export const listChatSessions = (limit = 30, offset = 0, report_id?: number) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (report_id != null) params.set("report_id", String(report_id));
  return request<Page<ChatSession>>(`/chat/sessions?${params.toString()}`);
};
export const getChatSession = (id: number) => request<ChatSession>(`/chat/sessions/${id}`);
export const getChatMessages = (id: number, limit = 100, offset = 0) =>
  request<Page<ChatMessage>>(`/chat/sessions/${id}/messages?limit=${limit}&offset=${offset}`);

// --- trends ---
export const listTrendableBiomarkers = () =>
  request<TrendableBiomarker[]>("/trends/biomarkers");
export const getTrend = (biomarker: string) =>
  request<TrendResponse>(`/trends?biomarker=${encodeURIComponent(biomarker)}`);

// --- export (binary PDF; bypasses the JSON request() helper) ---
export async function exportReportPdf(reportId: number, includeChat = false): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/export`, {
      method: "POST",
      headers,
      body: JSON.stringify({ report_id: reportId, include_chat: includeChat }),
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server. Is the backend running?");
  }
  if (!res.ok) {
    if (res.status === 401 && token) {
      clearToken();
      if (typeof window !== "undefined") window.dispatchEvent(new Event("medexplain:unauthorized"));
    }
    const data = await res.json().catch(() => ({}));
    const err = (data?.error ?? {}) as { code?: string; message?: string };
    throw new ApiError(res.status, err.code ?? "error", err.message ?? res.statusText);
  }
  return res.blob();
}
