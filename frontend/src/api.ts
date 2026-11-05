export interface Finding {
  severity: string;
  category: string;
  file?: string;
  line?: number;
  title?: string;
  description?: string;
  evidence?: string;
  recommendation?: string;
}

export interface Risk {
  total?: number;
  security?: number;
  code_quality?: number;
  dependency?: number;
  testing?: number;
  api_compatibility?: number;
}

export interface ReleaseReport {
  release_id: string;
  repository: string;
  title: string;
  risk?: Risk;
  decision: string;
  findings?: Finding[];
  deployment_checklist?: string[];
  rollback_plan?: string[];
  human_approval_note?: string;
}

export interface DecisionResponse {
  release_id: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const API_KEY = import.meta.env.VITE_API_KEY || "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (API_KEY) headers.set("X-API-Key", API_KEY);

  const response = await fetch(API_BASE + path, { ...options, headers });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || payload.error || "Request failed (" + response.status + ")");
  }

  return payload as T;
}

export const api = {
  health: () => request<Record<string, unknown>>("/health"),
  getReport: (id: string) =>
    request<ReleaseReport>("/api/releases/" + encodeURIComponent(id) + "/report"),
  approve: (id: string, note: string) =>
    request<DecisionResponse>("/api/releases/" + encodeURIComponent(id) + "/approve", {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  reject: (id: string, note: string) =>
    request<DecisionResponse>("/api/releases/" + encodeURIComponent(id) + "/reject", {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
};
