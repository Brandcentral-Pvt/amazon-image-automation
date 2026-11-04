"use client";

import { MainLayout } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Table } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Tabs, TabPanel } from "@/components/ui/Tabs";
import { RefreshCw, AlertCircle, CheckCircle, Settings, Zap, Shield, AlertTriangle, FileText, Trash2, Eye, BarChart } from "lucide-react";
import { formatRelativeTime, formatBytes } from "@/lib/utils";

const watermarkJobs = [
  { id: "wm-001", asin: "B0D44XVV2F", image: "Slot 2 - Back View", status: "completed", method: "sparkle", probeBefore: 0.87, probeAfter: 0.02, duration: "12.4s", created: "2024-01-15T10:38:00Z" },
  { id: "wm-002", asin: "B0D44XVV2F", image: "Slot 3 - Side View", status: "completed", method: "sparkle", probeBefore: 0.91, probeAfter: 0.01, duration: "11.8s", created: "2024-01-15T10:41:00Z" },
  { id: "wm-003", asin: "B0GLGBDVJY", image: "Slot 5 - Lifestyle", status: "completed", method: "near-match", probeBefore: 0.57, probeAfter: 0.57, duration: "13.1s", created: "2024-01-14T14:28:00Z" },
  { id: "wm-004", asin: "B0GLGBDVJY", image: "Slot 6 - Styling", status: "completed", method: "near-match", probeBefore: 0.62, probeAfter: 0.62, duration: "12.7s", created: "2024-01-14T14:31:00Z" },
  { id: "wm-005", asin: "B0CP9MK37V", image: "Slot 3 - Side View", status: "failed", method: "sparkle", probeBefore: 0.78, probeAfter: 0.78, duration: "0s", created: "2024-01-15T10:40:00Z", error: "Inpainting failed" },
  { id: "wm-006", asin: "B0CZRF18MK", image: "Slot 5 - Lifestyle", status: "completed", method: "sparkle", probeBefore: 0.84, probeAfter: 0.03, duration: "14.2s", created: "2024-01-11T11:22:00Z" },
];

export default function WatermarkPage() {
  return (
    <MainLayout title="Watermark Removal" subtitle="Monitor and manage Veo/Gemini sparkle removal">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="heading-md font-semibold">Watermark Removal</h2>
            <p className="text-body-sm text-surface-500">Veo/Gemini sparkle detection & inpainting pipeline</p>
          </div>
          <div className="flex items-center gap-3">
            <button className="px-4 py-2 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">
              <RefreshCw className="w-4 h-4 mr-2" /> Re-scan All
            </button>
            <button className="px-4 py-2 bg-brand-500 text-white rounded-lg hover:bg-brand-600 flex items-center gap-2">
              <Zap className="w-4 h-4" /> Run Cleanup
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="card p-6">
            <p className="text-body-sm text-surface-500">Total Processed</p>
            <p className="heading-lg font-semibold text-surface-900 mt-1">2,847</p>
            <div className="flex items-center gap-1 mt-2">
              <TrendingUp className="w-4 h-4 text-success-600" />
              <span className="text-body-sm font-medium text-success-600">+12.3%</span>
              <span className="text-body-sm text-surface-500">vs last week</span>
            </div>
          </div>
          <div className="card p-6">
            <p className="text-body-sm text-surface-500">Sparkles Removed</p>
            <p className="heading-lg font-semibold text-surface-900 mt-1">2,841</p>
            <div className="flex items-center gap-1 mt-2">
              <TrendingUp className="w-4 h-4 text-success-600" />
              <span className="text-body-sm font-medium text-success-600">+11.8%</span>
              <span className="text-body-sm text-surface-500">vs last week</span>
            </div>
          </div>
          <div className="card p-6">
            <p className="text-body-sm text-surface-500">Near-match Fallbacks</p>
            <p className="heading-lg font-semibold text-surface-900 mt-1">234</p>
            <div className="flex items-center gap-1 mt-2">
              <TrendingDown className="w-4 h-4 text-error-600" />
              <span className="text-body-sm font-medium text-error-600">-5.2%</span>
              <span className="text-body-sm text-surface-500">vs last week</span>
            </div>
          </div>
          <div className="card p-6">
            <p className="text-body-sm text-surface-500">Failed</p>
            <p className="heading-lg font-semibold text-surface-900 mt-1">6</p>
            <div className="flex items-center gap-1 mt-2">
              <Minus className="w-4 h-4 text-surface-500" />
              <span className="text-body-sm font-medium text-surface-500">0%</span>
              <span className="text-body-sm text-surface-500">this week</span>
            </div>
          </div>
        </div>

        <div className="card p-6 mb-6">
          <h3 className="heading-md font-semibold mb-4">Engine Status</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-surface-50 rounded-lg">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg bg-success-50 flex items-center justify-center">
                  <CheckCircle className="w-5 h-5 text-success-600" />
                </div>
                <div>
                  <p className="font-medium text-surface-900">LaMa ONNX</p>
                  <p className="text-body-sm text-surface-500">Model loaded</p>
                </div>
              </div>
              <div className="space-y-2 text-body-sm">
                <div className="flex justify-between"><span>Model</span><span className="font-medium">lama_fp32.onnx (198 MB)</span></div>
                <div className="flex justify-between"><span>Device</span><span className="font-medium">CPU</span></div>
                <div className="flex justify-between"><span>Threads</span><span className="font-medium">Auto (8)</span></div>
                <div className="flex justify-between"><span>Provider</span><span className="font-medium">CPUExecutionProvider</span></div>
              </div>
            </div>

            <div className="p-4 bg-surface-50 rounded-lg">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-brand-600" />
                </div>
                <div>
                  <p className="font-medium text-surface-900">Detection Engine</p>
                  <p className="text-body-sm text-surface-500">Sparkle template matcher</p>
                </div>
              </div>
              <div className="space-y-2 text-body-sm">
                <div className="flex justify-between"><span>Primary gate (IoU)</span><span className="font-medium">0.70</span></div>
                <div className="flex justify-between"><span>Near-match gate</span><span className="font-medium">0.55 - 0.70</span></div>
                <div className="flex justify-between"><span>Family gate</span><span className="font-medium">0.60</span></div>
                <div className="flex justify-between"><span>Ghost threshold</span><span className="font-medium">3.0 grey levels</span></div>
              </div>
            </div>

            <div className="p-4 bg-surface-50 rounded-lg">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg bg-info-50 flex items-center justify-center">
                  <Settings className="w-5 h-5 text-info-600" />
                </div>
                <div>
                  <p className="font-medium text-surface-900">Processing Config</p>
                  <p className="text-body-sm text-surface-500">Runtime parameters</p>
                </div>
              </div>
              <div className="space-y-2 text-body-sm">
                <div className="flex justify-between"><span>Timeout per image</span><span className="font-medium">180s</span></div>
                <div className="flex justify-between"><span>Re-fill passes</span><span className="font-medium">1 (pad 14)</span></div>
                <div className="flex justify-between"><span>Provenance copy</span><span className="font-medium">Enabled</span></div>
                <div className="flex justify-between"><span>Fail-safe</span><span className="font-medium">Never blocks run</span></div>
              </div>
            </div>
          </div>
        </div>

        <div className="card p-0">
          <div className="flex border-b border-surface-200">
            <button className="tab px-4 py-3 font-medium text-surface-500 border-b-2 border-transparent hover:text-surface-700 hover:border-surface-300">Jobs (2847)</button>
            <button className="tab px-4 py-3 font-medium text-surface-500 border-b-2 border-transparent hover:text-surface-700 hover:border-surface-300">Queue (3)</button>
            <button className="tab px-4 py-3 font-medium text-surface-500 border-b-2 border-transparent hover:text-surface-700 hover:border-surface-300">Failed (6)</button>
            <button className="tab px-4 py-3 font-medium text-surface-500 border-b-2 border-transparent hover:text-surface-700 hover:border-surface-300">Statistics</button>
          </div>
          <div className="p-0">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-50">
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">Job ID</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">ASIN</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">Image</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">Method</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">Probe Before</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">Probe After</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">Duration</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 border-b border-surface-200">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr className="hover:bg-surface-50 border-b border-surface-100">
                  <td className="px-4 py-3 font-mono text-body-sm">wm-001</td>
                  <td className="px-4 py-3">B0D44XVV2F</td>
                  <td className="px-4 py-3">Slot 2 - Back View</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-success-50 text-success-700 text-caption rounded-full">Completed</span></td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-info-50 text-info-700 text-caption rounded-full">sparkle</span></td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.87</td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.02</td>
                  <td className="px-4 py-3">12.4s</td>
                  <td className="px-4 py-3">
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="View"><Eye className="w-4 h-4" /></button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Retry"><RefreshCw className="w-4 h-4" /></Button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Delete"><Trash2 className="w-4 h-4" /></Button>
                  </td>
                </tr>
                <tr className="hover:bg-surface-50 border-b border-surface-100">
                  <td className="px-4 py-3 font-mono text-body-sm">wm-002</td>
                  <td className="px-4 py-3">B0D44XVV2F</td>
                  <td className="px-4 py-3">Slot 3 - Side View</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-success-50 text-success-700 text-caption rounded-full">Completed</span></td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-info-50 text-info-700 text-caption rounded-full">sparkle</span></td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.91</td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.01</td>
                  <td className="px-4 py-3">11.8s</td>
                  <td className="px-4 py-3">
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="View"><Eye className="w-4 h-4" /></button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Retry"><RefreshCw className="w-4 h-4" /></Button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Delete"><Trash2 className="w-4 h-4" /></Button>
                  </td>
                </tr>
                <tr className="hover:bg-surface-50 border-b border-surface-100">
                  <td className="px-4 py-3 font-mono text-body-sm">wm-003</td>
                  <td className="px-4 py-3">B0GLGBDVJY</td>
                  <td className="px-4 py-3">Slot 5 - Lifestyle</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-success-50 text-success-700 text-caption rounded-full">Completed</span></td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-warning-50 text-warning-700 text-caption rounded-full">near-match</span></td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.57</td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.57</td>
                  <td className="px-4 py-3">13.1s</td>
                  <td className="px-4 py-3">
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="View"><Eye className="w-4 h-4" /></button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Retry"><RefreshCw className="w-4 h-4" /></Button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Delete"><Trash2 className="w-4 h-4" /></Button>
                  </td>
                </tr>
                <tr className="hover:bg-surface-50 border-b border-surface-100">
                  <td className="px-4 py-3 font-mono text-body-sm">wm-004</td>
                  <td className="px-4 py-3">B0GLGBDVJY</td>
                  <td className="px-4 py-3">Slot 6 - Styling</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-success-50 text-success-700 text-caption rounded-full">Completed</span></td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-warning-50 text-warning-700 text-caption rounded-full">near-match</span></td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.62</td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.62</td>
                  <td className="px-4 py-3">12.7s</td>
                  <td className="px-4 py-3">
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="View"><Eye className="w-4 h-4" /></button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Retry"><RefreshCw className="w-4 h-4" /></Button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Delete"><Trash2 className="w-4 h-4" /></Button>
                  </td>
                </tr>
                <tr className="hover:bg-error-50 border-b border-surface-100">
                  <td className="px-4 py-3 font-mono text-body-sm">wm-005</td>
                  <td className="px-4 py-3">B0CP9MK37V</td>
                  <td className="px-4 py-3">Slot 3 - Side View</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-error-50 text-error-700 text-caption rounded-full">Failed</span></td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-info-50 text-info-700 text-caption rounded-full">sparkle</span></td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.78</td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.78</td>
                  <td className="px-4 py-3">0s</td>
                  <td className="px-4 py-3">
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="View"><Eye className="w-4 h-4" /></button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Retry"><RefreshCw className="w-4 h-4" /></Button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Delete"><Trash2 className="w-4 h-4" /></Button>
                  </td>
                </tr>
                <tr className="hover:bg-surface-50 border-b border-surface-100">
                  <td className="px-4 py-3 font-mono text-body-sm">wm-006</td>
                  <td className="px-4 py-3">B0CZRF18MK</td>
                  <td className="px-4 py-3">Slot 5 - Lifestyle</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-success-50 text-success-700 text-caption rounded-full">Completed</span></td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 bg-info-50 text-info-700 text-caption rounded-full">sparkle</span></td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.84</td>
                  <td className="px-4 py-3 font-mono text-body-sm">0.03</td>
                  <td className="px-4 py-3">14.2s</td>
                  <td className="px-4 py-3">
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="View"><Eye className="w-4 h-4" /></button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Retry"><RefreshCw className="w-4 h-4" /></Button>
                    <button className="p-2 text-surface-400 hover:text-surface-600" aria-label="Delete"><Trash2 className="w-4 h-4" /></Button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}