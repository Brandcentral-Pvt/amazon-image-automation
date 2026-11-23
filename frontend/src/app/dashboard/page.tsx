"use client";

import { MainLayout } from "@/components/layout";
import { MetricCard } from "@/components/charts/MetricsCard";
import { Table } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import { StepProgress } from "@/components/ui/Progress";
import { ScrollArea } from "@/components/ui/ScrollArea";
import { Tabs, TabPanel } from "@/components/ui/Tabs";
import { Avatar, AvatarGroup } from "@/components/ui/Avatar";
import { TrendingUp, TrendingDown, Database, Zap, Image, CheckCircle, AlertCircle, Clock, MoreHorizontal, Download, Eye, Edit, Trash2, RefreshCw, Play, Pause, Square } from "lucide-react";
import { formatRelativeTime, formatNumber } from "@/lib/utils";

const recentASINs = [
  { asin: "B0D44XVV2F", title: "BHARVITA Women's Cotton Embroidered Chikankari", brand: "BHARVITA", status: "completed", slots: 8, completed: 8, created: "2024-01-15T10:30:00Z", progress: 100 },
  { asin: "B0GLGBDVJY", title: "Amayra Women's Pure Cotton A-Line Kurta Set", brand: "Amayra", status: "completed", slots: 8, completed: 8, created: "2024-01-14T14:22:00Z", progress: 100 },
  { asin: "B0CP9MK37V", title: "ROYALICA Chinon Silk Sequence Zari Anarkali", brand: "ROYALICA", status: "generating", slots: 8, completed: 3, created: "2024-01-13T09:15:00Z", progress: 37 },
  { asin: "B0B4PZMWVG", title: "ROYALICA Women's Georgette Floral Embroidered", brand: "ROYALICA", status: "queued", slots: 8, completed: 0, created: "2024-01-12T16:45:00Z", progress: 0 },
  { asin: "B0CZRF18MK", title: "ROYALICA Women's Trousers", brand: "ROYALICA", status: "failed", slots: 8, completed: 5, created: "2024-01-11T11:20:00Z", progress: 62 },
  { asin: "B0CK4HX5RS", title: "ROYALICA Women's Vichitra Silk Blend Kurta", brand: "ROYALICA", status: "completed", slots: 8, completed: 8, created: "2024-01-10T08:30:00Z", progress: 100 },
  { asin: "B0CLRPLR4D", title: "ROYALICA Women Regular Fit Self Design Casual Shirt", brand: "ROYALICA", status: "generating", slots: 8, completed: 6, created: "2024-01-09T13:45:00Z", progress: 75 },
  { asin: "B0CGNJ927C", title: "ROYALICA Boy's Cotton Solid Regular Mens Kurta", brand: "ROYALICA", status: "completed", slots: 8, completed: 8, created: "2024-01-08T10:00:00Z", progress: 100 },
];

const stats = [
  { title: "Total ASINs", value: 24, change: 12.5, changeLabel: "vs last week", icon: <Database className="w-6 h-6" />, iconColor: "brand", trend: "up" },
  { title: "Completed Today", value: 3, change: -2, changeLabel: "vs yesterday", icon: <CheckCircle className="w-6 h-6" />, iconColor: "success", trend: "down" },
  { title: "Images Generated", value: 156, change: 23.1, changeLabel: "vs last week", icon: <Image className="w-6 h-6" />, iconColor: "info", trend: "up" },
  { title: "Watermarks Removed", value: 42, change: 8.3, changeLabel: "vs last week", icon: <Zap className="w-6 h-6" />, iconColor: "warning", trend: "up" },
];

const generationSteps = [
  { label: "Upload ASINs", description: "Upload CSV or enter ASINs manually", completed: true },
  { label: "Scrape Products", description: "Fetch product data and base images", completed: true },
  { label: "Build Prompts", description: "Generate prompts from gallery + AIIE", completed: true },
  { label: "Generate Images", description: "Send to Gemini & download results", completed: false, current: true },
  { label: "Watermark Removal", description: "Clean sparkles via Veo remover", completed: false },
  { label: "Final Verification", description: "QA check & manifest update", completed: false },
];

export default function DashboardPage() {
  return (
    <MainLayout title="Dashboard" subtitle="Overview of your Amazon image automation pipeline">
      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((stat, i) => (
          <MetricCard key={i} {...stat} />
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Recent ASINs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Generation Pipeline */}
          <Card>
            <CardHeader>
              <CardTitle>Active Generation Pipeline</CardTitle>
            </CardHeader>
            <CardContent>
              <StepProgress steps={generationSteps} />
            </CardContent>
          </Card>

          {/* Recent ASINs Table */}
          <Card>
            <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <CardTitle>Recent ASINs</CardTitle>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm"><RefreshCw className="w-4 h-4 mr-1" /> Refresh</Button>
                <Button variant="primary" size="sm"><Download className="w-4 h-4 mr-1" /> Export CSV</Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table
                  columns={[
                    { key: "asin", header: "ASIN", accessor: "asin", width: "120px" },
                    { key: "title", header: "Product Title", accessor: (row) => (
                      <div className="max-w-xs">
                        <p className="font-medium text-surface-900 truncate">{row.title}</p>
                        <p className="text-body-sm text-surface-500 truncate">{row.brand}</p>
                      </div>
                    ) },
                    { key: "status", header: "Status", accessor: "status", width: "120px", render: (val) => {
                      const statusConfig = {
                        completed: { label: "Completed", variant: "success" as const },
                        generating: { label: "Generating", variant: "info" as const },
                        queued: { label: "Queued", variant: "warning" as const },
                        failed: { label: "Failed", variant: "error" as const },
                      };
                      const config = statusConfig[val as keyof typeof statusConfig] || { label: val, variant: "neutral" as const };
                      return <Badge variant={config.variant} size="sm">{config.label}</Badge>;
                    }},
                    { key: "progress", header: "Progress", accessor: "progress", width: "140px", render: (val) => (
                      <div className="w-full">
                        <div className="progress h-2">
                          <div className="progress-bar" style={{ width: `${val}%` }} />
                        </div>
                        <p className="text-caption text-surface-500 mt-1 text-right">{val}%</p>
                      </div>
                    ) },
                    { key: "slots", header: "Slots", accessor: (row) => `${row.completed}/${row.slots}`, width: "100px" },
                    { key: "created", header: "Created", accessor: (row) => formatRelativeTime(row.created), width: "120px" },
                    { key: "actions", header: "Actions", accessor: (row) => (
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" aria-label="View details"><Eye className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" aria-label="Retry"><RefreshCw className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" aria-label="Download"><Download className="w-4 h-4" /></Button>
                      </div>
                    ), width: "100px" },
                  ]}
                  data={recentASINs}
                  keyExtractor={(row) => row.asin}
                  striped
                  hoverable
                  rowClassName={(row) => row.status === "failed" ? "bg-error-50" : ""}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Stats & Quick Actions */}
        <div className="space-y-6">
          {/* System Health */}
          <Card>
            <CardHeader>
              <CardTitle>System Health</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  { label: "Amazon Scraper", status: "healthy" as const, detail: "Last check: 2 min ago" },
                  { label: "Gemini Web", status: "healthy" as const, detail: "Last check: 1 min ago" },
                  { label: "Watermark Engine", status: "healthy" as const, detail: "Last check: 30 sec ago" },
                  { label: "Storage", status: "warning" as const, detail: "78% used (234 GB / 300 GB)" },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-surface-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <Badge variant={item.status === "healthy" ? "success" : item.status === "warning" ? "warning" : "error"} dot>
                        {item.label}
                      </Badge>
                    </div>
                    <span className="text-body-sm text-surface-500">{item.detail}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <Button variant="outline" className="h-20 flex flex-col items-center gap-2">
                  <Database className="w-6 h-6" />
                  <span className="text-body-sm">Add ASINs</span>
                </Button>
                <Button variant="outline" className="h-20 flex flex-col items-center gap-2">
                  <Zap className="w-6 h-6" />
                  <span className="text-body-sm">Start Generation</span>
                </Button>
                <Button variant="outline" className="h-20 flex flex-col items-center gap-2">
                  <Image className="w-6 h-6" />
                  <span className="text-body-sm">View Images</span>
                </Button>
                <Button variant="outline" className="h-20 flex flex-col items-center gap-2">
                  <Zap className="w-6 h-6" />
                  <span className="text-body-sm">Clean Watermarks</span>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  { action: "Generation completed", target: "ASIN B0D44XVV2F", detail: "All 8 slots generated successfully", time: "5 min ago", type: "success" },
                  { action: "Watermark cleaned", target: "ASIN B0GLGBDVJY", detail: "3 sparkles removed (slots 2, 5, 6)", time: "1 hour ago", type: "info" },
                  { action: "Generation failed", target: "ASIN B0CP9MK37V", detail: "Slot 3 - Gemini quota exceeded", time: "3 hours ago", type: "error" },
                  { action: "ASINs uploaded", target: "CSV import", detail: "12 new ASINs added to queue", time: "6 hours ago", type: "info" },
                  { action: "Watermark sweep", target: "Batch cleanup", detail: "2 ghost marks detected & removed", time: "1 day ago", type: "warning" },
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-surface-50 rounded-lg">
                    <Badge variant={item.type} dot>{item.action}</Badge>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-surface-900">{item.target}</p>
                      <p className="text-body-sm text-surface-500">{item.detail}</p>
                    </div>
                    <span className="text-caption text-surface-400">{item.time}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </MainLayout>
  );
}