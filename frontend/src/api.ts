// Thin client for the local FastAPI server (http://127.0.0.1:<port>/api/v1).
// Electron injects the port via window.shopDesktop; when the built app is served by the
// backend itself the API is same-origin; in `npm run dev` we default to 127.0.0.1:8765.
declare global {
  interface Window {
    shopDesktop?: {
      apiBase?: string;
      chooseFolder?: () => Promise<string | null>;
      chooseBackupFile?: () => Promise<string | null>;
      printReceipt?: (size: string) => Promise<boolean>;
      savePdf?: (size: string, name: string) => Promise<string | null>;
    };
  }
}

const envBase = (import.meta as any).env?.VITE_API_BASE as string | undefined;
export const API_BASE: string =
  window.shopDesktop?.apiBase ||
  envBase ||
  (location.protocol.startsWith("http") && location.port !== "5173" && location.port !== "8443"
    ? `${location.origin}/api/v1`
    : "http://127.0.0.1:8765/api/v1");

const TOKEN_KEY = "shop.token";
export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) =>
  t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Serveur local indisponible.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.message || (Array.isArray(data?.detail) ? "Données invalides." : "Erreur.");
    if (res.status === 401 && data?.code === "SESSION_EXPIRED") {
      setToken(null);
      window.dispatchEvent(new Event("shop:session-expired"));
    }
    throw new ApiError(res.status, data?.code || "ERROR", msg);
  }
  return data as T;
}

export const api = {
  get: <T = any>(p: string) => request<T>("GET", p),
  post: <T = any>(p: string, b: unknown = {}) => request<T>("POST", p, b),
  patch: <T = any>(p: string, b: unknown = {}) => request<T>("PATCH", p, b),
};

/** Server money/quantities are exact decimal strings; the UI only displays them. */
export const num = (v: unknown): number => (v === null || v === undefined || v === "" ? 0 : Number(v));

export async function waitForServer(tries = 40): Promise<boolean> {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(`${API_BASE}/health`);
      if (r.ok) return true;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

export type SessionUser = {
  id: number;
  name: string;
  username: string;
  phone: string | null;
  role: "OWNER" | "WORKER" | "DDS_ADMIN";
  active: boolean;
  can_receive_stock: boolean;
  can_sell_credit: boolean;
  has_pin: boolean;
};

export const errMsg = (e: unknown, fallback = "Erreur") =>
  e instanceof ApiError ? e.message : fallback;

export async function downloadDailyExcel(opts?: {
  period?: "day" | "week";
  dateFrom?: string;
  dateTo?: string;
}): Promise<string> {
  const params = new URLSearchParams();
  if (opts?.period) params.set("period", opts.period);
  if (opts?.dateFrom) params.set("date_from", opts.dateFrom);
  if (opts?.dateTo) params.set("date_to", opts.dateTo);
  const q = params.toString() ? `?${params.toString()}` : "";
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/reports/daily-excel${q}`, { headers });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data?.code || "EXPORT_ERROR", data?.message || "Erreur d'export Excel.");
  }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const match = cd.match(/filename="?([^"]+)"?/i);
  const fallback =
    opts?.dateFrom && opts?.dateTo && opts.dateFrom !== opts.dateTo
      ? `Rapport_${opts.dateFrom}_au_${opts.dateTo}.xlsx`
      : `Rapport_${opts?.dateFrom || new Date().toISOString().slice(0, 10)}.xlsx`;
  const filename = match ? match[1] : fallback;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  return filename;
}
