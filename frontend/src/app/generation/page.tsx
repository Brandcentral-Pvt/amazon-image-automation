"use client";

import { MainLayout } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Table } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Progress, StepProgress } from "@/components/ui/Progress";
import { Tabs, TabPanel } from "@/components/ui/Tabs";
import { ScrollArea } from "@/components/ui/ScrollArea";
import { Upload, Play, Pause, RefreshCw, Download, Eye, Trash2, ChevronDown, AlertCircle, Clock, CheckCircle, FileText, Zap } from "lucide-react";
import { formatRelativeTime, formatNumber } from "@/lib/utils";

const queueItems = [
  { id: "job-001", asin: "B0CP9MK37V", title: "ROYALICA Chinon Silk Anarkali", status: "generating", slot: 3, progress: 37, started: "2024-01-15T10:30:00Z", retries: 0 },
  { id: "job-002", asin: "B0B4PZMWVG", title: "ROYALICA Georgette Floral", status: "queued", slot: 0, progress: 0, started: "2024-01-15T10:35:00Z", retries: 0 },
  { id: "job-003", asin: "B0CZRF18MK", title: "ROYALICA Women's Trousers", status: "failed", slot: 5, progress: 62, started: "2024-01-15T10:40:00Z", retries: 2, error: "Gemini quota exceeded" },
  { id: "job-004", asin: "B0CLRPLR4D", title: "ROYALICA Casual Shirt", status: "generating", slot: 6, progress: 75, started: "2024-01-15T10:45:00Z", retries: 0 },
  { id: "job-005", asin: "B0CGNJ927C", title: "ROYALICA Boy's Cotton Kurta", status: "completed", slot: 8, progress: 100, started: "2024-01-15T10:50:00Z", retries: 0 },
];

const historyItems = [
  { asin: "B0D44XVV2F", title: "BHARVITA Chikankari Kurta", completed: "2024-01-14T14:22:00Z", slots: 8, duration: "12m 34s", status: "success" },
  { asin: "B0GLGBDVJY", title: "Amayra Cotton Kurta Set", completed: "2024-01-13T11:15:00Z", slots: 8, duration: "15m 12s", status: "success" },
  { asin: "B0CK4HX5RS", title: "ROYALICA Silk Kurta", completed: "2024-01-12T08:30:00Z", slots: 8, duration: "11m 45s", status: "success" },
  { asin: "B0CGNJ927C", title: "ROYALICA Boy's Kurta", completed: "2024-01-11T10:00:00Z", slots: 8, duration: "13m 22s", status: "success" },
  { asin: "B0CZRF18MK", title: "ROYALICA Trousers", completed: "2024-01-10T14:45:00Z", slots: 5, duration: "8m 30s", status: "partial" },
];

const generationSteps = [
  { label: "Upload & Validate ASINs", description: "Parse CSV/JSON, validate ASINs", completed: true },
  { label: "Scrape Product Data", description: "Fetch titles, images, attributes", completed: true },
  { label: "Download Base Images", description: "Download hi-res product images", completed: true },
  { label: "Build Prompts", description: "AIIE + Gallery prompts per slot", completed: true },
  { label: "Generate Images", description: "Send to Gemini (8 slots each)", completed: false, current: true },
  { label: "Watermark Removal", description: "Sparkle detection & inpainting", completed: false },
  { label: "Verify & Package", description: "QA check, manifest, manifest", completed: false },
];

export default function GenerationPage() {
  return (
    <MainLayout title="Generation" subtitle="Manage and monitor image generation jobs">
      <div className="space-y-6">
        {/* Header Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="heading-md font-semibold">Generation Queue</h2>
            <p className="text-body-sm text-surface-500">Monitor and manage image generation jobs</p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline">
              <FileText className="w-4 h-4 mr-2" />
              Import ASINs
            </Button>
            <Button variant="primary">
              <Zap className="w-4 h-4 mr-2" />
              Start Generation
            </Button>
          </div>
        </div>

        {/* Pipeline Overview */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Generation Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <StepProgress steps={generationSteps} />
          </CardContent>
        </Card>

        {/* Tabs */}
        <Tabs tabs={[
          { key: "queue", label: "Queue", icon: <Clock className="w-4 h-4" />, count: 5 },
          { key: "active", label: "Active", icon: <Play className="w-4 h-4" />, count: 2 },
          { key: "completed", label: "Completed", icon: <CheckCircle className="w-4 h-4" />, count: 142 },
          { key: "failed", label: "Failed", icon: <AlertCircle className="w-4 h-4" />, count: 3 },
          { key: "history", label: "History", icon: <FileText className="w-4 h-4" />, count: 145 },
        ]} onChange={(key) => {}} className="mb-6">
          <TabPanel active={true}>
            <Card>
              <CardContent className="p-0">
                <Table
                  columns={[
                    { key: "asin", header: "ASIN", accessor: "asin", width: "130px" },
                    { key: "title", header: "Product", accessor: (row) => (
                      <div>
                        <p className="font-medium text-surface-900">{row.title}</p>
                        <p className="text-body-sm text-surface-500">{row.asin}</p>
                      </div>
                    ) },
                    { key: "status", header: "Status", accessor: "status", width: "140px", render: (val) => {
                      const configs = {
                        generating: { label: "Generating", variant: "info" as const, icon: <Play className="w-3 h-3 mr-1" /> },
                        queued: { label: "Queued", variant: "warning" as const, icon: <Clock className="w-3 h-3 mr-1" /> },
                        completed: { label: "Completed", variant: "success" as const, icon: <CheckCircle className="w-3 h-3 mr-1" /> },
                        failed: { label: "Failed", variant: "error" as const, icon: <AlertCircle className="w-3 h-3 mr-1" /> },
                      };
                      const c = configs[val as keyof typeof configs] || { label: val, variant: "neutral" as const };
                      return <Badge variant={c.variant} size="sm">{c.icon} {c.label}</Badge>;
                    }},
                    { key: "progress", header: "Progress", accessor: "progress", width: "180px", render: (val) => (
                      <div className="flex items-center gap-3 w-full">
                        <div className="flex-1"><Progress value={val} size="sm" showLabel /></div>
                        <span className="text-body-sm font-mono text-surface-500 w-14 text-right">{val}%</span>
                      </div>
                    )},
                    { key: "slot", header: "Slot", accessor: (row) => `${row.slot}/8`, width: "80px" },
                    { key: "started", header: "Started", accessor: (row) => formatRelativeTime(row.started), width: "140px" },
                    { key: "retries", header: "Retries", accessor: "retries", width: "80px", render: (val) => val > 0 ? <Badge variant="warning" size="sm">{val}</Badge> : "-" },
                    { key: "actions", header: "Actions", accessor: (row) => (
                      <div className="flex items-center gap-1">
                        {row.status === "generating" && (
                          <Button variant="ghost" size="icon" aria-label="Pause"><Pause className="w-4 h-4" /></Button>
                        )}
                        {row.status === "queued" && (
                          <Button variant="ghost" size="icon" aria-label="Start"><Play className="w-4 h-4" /></Button>
                        )}
                        {row.status === "failed" && (
                          <Button variant="ghost" size="icon" aria-label="Retry"><RefreshCw className="w-4 h-4" /></Button>
                        )}
                        {row.status === "completed" && (
                          <Button variant="ghost" size="icon" aria-label="View"><Eye className="w-4 h-4" /></Button>
                        )}
                        <Button variant="ghost" size="icon" aria-label="Delete"><Trash2 className="w-4 h-4" /></Button>
                      </div>
                    ), width: "140px" },
                  ]}
                  data={queueItems}
                  keyExtractor={(row) => row.id}
                  striped
                  hoverable
                  emptyMessage="No jobs in queue"
                />
              </div>
            </Card>
          </TabPanel>
          <TabPanel active={false}>
            <Card>
              <CardContent className="p-0">
                <Table
                  columns={[
                    { key: "asin", header: "ASIN", accessor: "asin", width: "130px" },
                    { key: "title", header: "Product", accessor: (row) => <div><p className="font-medium">{row.title}</p></div> },
                    { key: "completed", header: "Completed", accessor: (row) => formatRelativeTime(row.completed), width: "140px" },
                    { key: "slots", header: "Slots", accessor: "slots", width: "80px" },
                    { key: "duration", header: "Duration", accessor: "duration", width: "120px" },
                    { key: "status", header: "Status", accessor: "status", width: "120px", render: (val) => {
                      const configs = {
                        success: { label: "Success", variant: "success" as const },
                        partial: { label: "Partial", variant: "warning" as const },
                      };
                      const c = configs[val as keyof typeof configs] || { label: val, variant: "neutral" as const };
                      return <Badge variant={c.variant} size="sm">{c.label}</Badge>;
                    }},
                    { key: "actions", header: "Actions", accessor: (row) => (
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" aria-label="View"><Eye className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" aria-label="Download"><Download className="w-4 h-4" /></Button>
                      </div>
                    ), width: "100px" },
                  ]}
                  data={historyItems}
                  keyExtractor={(row) => row.asin}
                  striped
                  hoverable
                />
              </div>
            </Card>
          </TabPanel>
        </Tabs>
      </div>
    </MainLayout>
  );
}

// Import missing components
import { Select } from "@/components/ui/Dropdown";
import { Dropdown } from "@/components/ui/Dropdown";