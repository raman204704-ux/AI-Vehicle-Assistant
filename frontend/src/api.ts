const API_BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000")
  .replace(/\/+$/, "");

const TOKEN_KEY = "motorly_access_token";

export interface User {
  id: number;
  email: string;
  is_active: boolean;
}

export interface Vehicle {
  id: number;
  vehicle_name: string;
  manufacturer: string;
  model: string;
  year: number;
  fuel_type: string;
  registration_number: string;
  current_odometer: number;
  created_at: string;
}

export interface VehicleInput {
  vehicle_name: string;
  manufacturer: string;
  model: string;
  year: number;
  fuel_type: string;
  registration_number: string;
  current_odometer: number;
}

export interface ServiceRecord {
  id: number;
  vehicle_id: number;
  source_document_id: number | null;
  service_date: string;
  odometer_reading: number;
  service_type: string;
  description: string | null;
  workshop_name: string | null;
  total_cost: number;
  source_type: string;
  created_at: string | null;
}

export interface ServiceRecordInput {
  service_date: string;
  odometer_reading: number;
  service_type: string;
  description: string | null;
  workshop_name: string | null;
  total_cost: number;
}

export interface ExpenseSummary {
  vehicle_id: number;
  total_expenses: number;
  total_transactions: number;
  average_expense: number;
}

export interface CategoryExpense {
  category: string;
  total_amount: number;
  transaction_count: number;
}

export interface MonthlyExpense {
  year: number;
  month: number;
  total_amount: number;
}

export interface YearlyExpense {
  year: number;
  total_amount: number;
}

export interface ServiceTypeExpense {
  service_type: string;
  total_amount: number;
  transaction_count: number;
}

export interface VehicleExpenseComparison {
  vehicle_id: number;
  vehicle_name: string;
  total_expenses: number;
}

export interface Reminder {
  id: number;
  vehicle_id: number;
  title: string;
  description: string | null;
  category: string;
  due_date: string | null;
  due_odometer: number | null;
  repeat_interval_months: number | null;
  repeat_interval_km: number | null;
  reminder_days_before: number;
  status: "active" | "completed" | "cancelled";
  is_enabled: boolean;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReminderInput {
  title: string;
  description: string | null;
  category: string;
  due_date: string | null;
  due_odometer: number | null;
  repeat_interval_months: number | null;
  repeat_interval_km: number | null;
  reminder_days_before: number;
}

export interface AppNotification {
  id: number;
  vehicle_id: number;
  reminder_id: number;
  title: string;
  message: string;
  notification_type: "upcoming" | "overdue";
  is_read: boolean;
  created_at: string;
}

export interface DocumentRecord {
  id: number;
  vehicle_id: number;
  file_name: string;
  file_type: string;
  file_size: number | null;
  document_type: string | null;
  processing_status: string;
  uploaded_at: string;
}

export interface Source {
  source_id: string;
  title: string;
  url: string;
  source_type: string;
  retrieved_at: string;
}

export interface AssistantResponse {
  question: string;
  answer: string;
  sources: Source[];
  documents_retrieved: number;
  documents_indexed: number;
  generated_at: string;
}

export interface MechanicResponse {
  session_id: number;
  answer: string;
  sources: Source[];
  created_at: string;
}

export interface DiagnosticSession {
  id: number;
  vehicle_id: number;
  title: string | null;
  status: "active" | "closed";
  created_at: string;
  updated_at: string;
}

export interface DiagnosticMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface MaintenancePrediction {
  rule_id: number;
  maintenance_type: string;
  status: "overdue" | "due_soon" | "not_due" | "unknown";
  last_service_date: string | null;
  last_service_odometer: number | null;
  current_odometer: number;
  next_due_odometer: number | null;
  remaining_km: number | null;
  next_due_date: string | null;
  remaining_days: number | null;
  source_title: string;
  source_url: string;
}

export interface MaintenancePredictionResponse {
  vehicle_id: number;
  vehicle_name: string;
  current_odometer: number;
  predictions: MaintenancePrediction[];
  generated_at: string;
}

function readErrorDetail(payload: unknown): string | null {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return null;
  }
  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  if (detail !== undefined) return JSON.stringify(detail);
  return null;
}

export function getToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  if (
    init.body !== undefined &&
    !(init.body instanceof FormData) &&
    !(init.body instanceof URLSearchParams) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new Error(
      `Can't reach the API at ${API_BASE}. Check that the backend is running.`,
    );
  }

  if (response.status === 204) return undefined as T;

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = readErrorDetail(payload);
    if (response.status === 401) {
      clearToken();
      window.dispatchEvent(new Event("motorly:unauthorized"));
    }
    throw new Error(detail ?? `Request failed with status ${response.status}`);
  }
  return payload as T;
}

export async function downloadDocument(documentId: number): Promise<Blob> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(
    `${API_BASE}/documents/${documentId}/download`,
    { headers },
  );
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new Error(readErrorDetail(payload) ?? "Could not download document");
  }
  return response.blob();
}

export function notifyNotificationsChanged(): void {
  window.dispatchEvent(new Event("motorly:notifications-updated"));
}
