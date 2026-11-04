/**
 * API client for the Amazon Image Automation backend.
 * Connects to the Python pipeline via REST API.
 */
import { ASIN, Slot, GenerationJob, WatermarkResult, PipelineStats, SystemHealth, ASINFilters, JobControlRequest, APIResponse, AppSettings } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private base: string;

  constructor(base: string = API_BASE) {
    this.base = base;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<APIResponse<T>> {
    const res = await fetch(`${this.base}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (!res.ok) {
      return { success: false, error: `API error: ${res.status}` };
    }

    return res.json();
  }

  // ASINs
  async listASINs(filters?: ASINFilters): Promise<ASIN[]> {
    const params = new URLSearchParams();
    if (filters?.search) params.set("search", filters.search);
    if (filters?.status) filters.status.forEach((s) => params.append("status", s));
    if (filters?.brand) filters.brand.forEach((b) => params.append("brand", b));
    if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
    if (filters?.dateTo) params.set("date_to", filters.dateTo);

    const res = await this.request<ASIN[]>(`/api/asins?${params.toString()}`);
    return res.success ? (res.data ?? []) : [];
  }

  async getASIN(asin: string): Promise<ASIN | null> {
    const res = await this.request<ASIN>(`/api/asins/${asin}`);
    return res.success ? (res.data ?? null) : null;
  }

  async addASINs(asins: string[]): Promise<boolean> {
    const res = await this.request<void>("/api/asins", {
      method: "POST",
      body: JSON.stringify({ asins }),
    });
    return res.success;
  }

  // Slots / Images
  async getSlots(asin: string): Promise<Slot[]> {
    const res = await this.request<Slot[]>(`/api/asins/${asin}/slots`);
    return res.success ? (res.data ?? []) : [];
  }

  async getImage(asin: string, slotId: string): Promise<string | null> {
    const res = await this.request<{ url: string }>(`/api/asins/${asin}/slots/${slotId}/image`);
    return res.success ? (res.data?.url ?? null) : null;
  }

  // Generation
  async startGeneration(asins: string[], notes?: string): Promise<{ jobId: string } | null> {
    const res = await this.request<{ job_id: string }>("/api/generate", {
      method: "POST",
      body: JSON.stringify({ asins, notes }),
    });
    if (!res.success || !res.data) return null;
    return { jobId: res.data.job_id };
  }

  async getJob(jobId: string): Promise<GenerationJob | null> {
    const res = await this.request<GenerationJob>(`/api/jobs/${jobId}`);
    return res.success ? (res.data ?? null) : null;
  }

  async listJobs(): Promise<GenerationJob[]> {
    const res = await this.request<GenerationJob[]>("/api/jobs");
    return res.success ? (res.data ?? []) : [];
  }

  async controlJob(action: JobControlRequest["action"], asin?: string, slotId?: string): Promise<boolean> {
    const res = await this.request<void>("/api/jobs/control", {
      method: "POST",
      body: JSON.stringify({ action, asin, slot_id: slotId }),
    });
    return res.success;
  }

  // Watermark
  async getWatermarkJobs(): Promise<WatermarkResult[]> {
    const res = await this.request<WatermarkResult[]>("/api/watermark/jobs");
    return res.success ? (res.data ?? []) : [];
  }

  async runWatermarkCleanup(asins: string[]): Promise<boolean> {
    const res = await this.request<void>("/api/watermark/clean", {
      method: "POST",
      body: JSON.stringify({ asins }),
    });
    return res.success;
  }

  // Stats / Health
  async getStats(): Promise<PipelineStats | null> {
    const res = await this.request<PipelineStats>("/api/stats");
    return res.success ? (res.data ?? null) : null;
  }

  async getSystemHealth(): Promise<SystemHealth | null> {
    const res = await this.request<SystemHealth>("/api/health");
    return res.success ? (res.data ?? null) : null;
  }

  // Settings
  async getSettings(): Promise<AppSettings | null> {
    const res = await this.request<AppSettings>("/api/settings");
    return res.success ? (res.data ?? null) : null;
  }

  async saveSettings(settings: AppSettings): Promise<boolean> {
    const res = await this.request<void>("/api/settings", {
      method: "POST",
      body: JSON.stringify(settings),
    });
    return res.success;
  }
}

export const api = new ApiClient();
export type { ASIN, Slot, GenerationJob, WatermarkResult, PipelineStats, SystemHealth, ASINFilters, JobControlRequest, AppSettings };
