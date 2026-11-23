// Core domain types matching the backend

export interface ASIN {
  asin: string;
  title: string;
  brand: string;
  category: string;
  price?: string;
  currency?: string;
  imageCount: number;
  status: ASINStatus;
  createdAt: string;
  updatedAt: string;
  lastError?: string;
}

export type ASINStatus =
  | "pending"
  | "scraping"
  | "scraped"
  | "generating"
  | "generated"
  | "cleaning"
  | "completed"
  | "failed"
  | "partial";

export interface Slot {
  id: string;
  order: number;
  title: string;
  intent: string;
  targetFile: string;
  source: "gallery" | "aiie" | "slots";
  galleryRef?: string;
  galleryTitle?: string;
  status: SlotStatus;
  file?: string;
  watermarkStatus?: WatermarkStatus;
  attempts?: number;
  error?: string;
  generatedAt?: string;
}

export type SlotStatus =
  | "pending"
  | "generating"
  | "generated"
  | "cleaning"
  | "completed"
  | "failed"
  | "skipped";

export type WatermarkStatus =
  | "removed"
  | "no-mark"
  | "error"
  | "skipped"
  | "disabled"
  | "ghost";

export interface GenerationJob {
  id: string;
  asin: string;
  status: JobStatus;
  progress: number;
  currentSlot?: string;
  slotsCompleted: number;
  slotsTotal: number;
  startedAt: string;
  completedAt?: string;
  error?: string;
}

export type JobStatus =
  | "queued"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export interface WatermarkResult {
  status: WatermarkStatus;
  method?: string;
  probeBefore?: number;
  probeAfter?: number;
  ghost?: boolean;
  verdict?: string;
  seconds?: number;
  detail?: string;
}

export interface PipelineStats {
  ok: number;
  failed: number;
  slotsOk: number;
  slotsFailed: number;
  totalTime: number;
}

export interface ASINFilters {
  search?: string;
  status?: ASINStatus[];
  dateFrom?: string;
  dateTo?: string;
  brand?: string[];
}

export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export interface DashboardMetrics {
  totalASINs: number;
  completedToday: number;
  inProgress: number;
  failed: number;
  totalImagesGenerated: number;
  avgGenerationTime: number;
  successRate: number;
  watermarkRemoved: number;
}

export interface SystemHealth {
  scraper: "healthy" | "degraded" | "down";
  gemini: "healthy" | "degraded" | "down";
  watermark: "healthy" | "degraded" | "down";
  storage: "healthy" | "warning" | "critical";
}

export interface Notification {
  id: string;
  type: "success" | "error" | "warning" | "info";
  title: string;
  message?: string;
  timestamp: string;
  read: boolean;
  actionUrl?: string;
}

// API Response types
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface JobControlRequest {
  action: "pause" | "resume" | "cancel" | "retry";
  asin?: string;
  slotId?: string;
}

// Settings types
export interface AppSettings {
  gemini: GeminiSettings;
  watermark: WatermarkSettings;
  scraper: ScraperSettings;
  output: OutputSettings;
  notifications: NotificationSettings;
}

export interface GeminiSettings {
  useOwnChromeProfile: boolean;
  chromeProfileName: string;
  chromeChannel: "chrome" | "chromium";
  maxReferenceImages: number;
  attachReferencesEverySlot: boolean;
  ensureImageModel: boolean;
  ensureImageModelEverySlot: boolean;
  aspectRatio: string;
  slotRetries: number;
  slotRetryDelaySec: [number, number];
  newChatPerSlot: boolean;
  sendMasterPrompt: boolean;
  generationTimeoutSec: number;
  uploadWaitSec: number;
  betweenSlotsSec: [number, number];
  blockWaitSec: number;
}

export interface WatermarkSettings {
  enabled: boolean;
  engineDir: string;
  python: string;
  model: string;
  device: "auto" | "cpu" | "cuda";
  threads: number;
  timeoutSec: number;
}

export interface ScraperSettings {
  domain: string;
  locale: string;
  maxGalleryImages: number;
  minImagePx: number;
  scrollPasses: number;
  pageTimeoutMs: number;
  delayBetweenAsins: [number, number];
}

export interface OutputSettings {
  root: string;
  keepBaseImages: boolean;
}

export interface NotificationSettings {
  emailEnabled: boolean;
  emailRecipients: string[];
  slackEnabled: boolean;
  slackWebhookUrl: string;
  notifyOnComplete: boolean;
  notifyOnError: boolean;
  notifyOnWatermarkGhost: boolean;
}

// WebSocket events
export interface WSMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: string;
}

export interface WSProgressPayload {
  jobId: string;
  asin: string;
  slotId: string;
  progress: number;
  status: SlotStatus;
  message?: string;
}

export interface WSCompletePayload {
  jobId: string;
  asin: string;
  stats: PipelineStats;
  error?: string;
}

export interface WSErrorPayload {
  jobId: string;
  asin: string;
  slotId?: string;
  error: string;
  retryable: boolean;
}