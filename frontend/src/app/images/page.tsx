"use client";

import { MainLayout } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Dropdown } from "@/components/ui/Dropdown";
import { Image, Download, Eye, Edit, Trash2, MoreHorizontal, Search, Filter, ChevronDown, RotateCcw, ZoomIn, ZoomOut, Move, Maximize, Minimize, ArrowUpRight, Sparkles } from "lucide-react";
import { formatRelativeTime, formatBytes } from "@/lib/utils";

const images = [
  { id: "img-001", asin: "B0D44XVV2F", slot: 1, title: "Hero - White Background", url: "/placeholder-1.jpg", size: 2450000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-15T10:35:00Z" },
  { id: "img-002", asin: "B0D44XVV2F", slot: 2, title: "Back View", url: "/placeholder-2.jpg", size: 2180000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-15T10:38:00Z" },
  { id: "img-003", asin: "B0D44XVV2F", slot: 3, title: "Side View", url: "/placeholder-3.jpg", size: 2320000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-15T10:41:00Z" },
  { id: "img-004", asin: "B0D44XVV2F", slot: 4, title: "Craft Story", url: "/placeholder-4.jpg", size: 2650000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-15T10:44:00Z" },
  { id: "img-005", asin: "B0D44XVV2F", slot: 5, title: "Lifestyle", url: "/placeholder-5.jpg", size: 2580000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-15T10:47:00Z" },
  { id: "img-006", asin: "B0D44XVV2F", slot: 6, title: "Styling Lookbook", url: "/placeholder-6.jpg", size: 2720000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-15T10:50:00Z" },
  { id: "img-007", asin: "B0D44XVV2F", slot: 7, title: "USP Infographic", url: "/placeholder-7.jpg", size: 2380000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-15T10:53:00Z" },
  { id: "img-008", asin: "B0D44XVV2F", slot: 8, title: "Product Guide", url: "/placeholder-8.jpg", size: 2120000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-15T10:56:00Z" },
  { id: "img-009", asin: "B0GLGBDVJY", slot: 1, title: "Hero - White Background", url: "/placeholder-9.jpg", size: 2340000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-14T14:25:00Z" },
  { id: "img-010", asin: "B0GLGBDVJY", slot: 2, title: "Back View", url: "/placeholder-10.jpg", size: 2100000, dimensions: "1600x1920", watermark: "removed", created: "2024-01-14T14:28:00Z" },
  { id: "img-011", asin: "B0GLGBDVJY", slot: 3, title: "Side View", url: "/placeholder-11.jpg", size: 2250000, dimensions: "1600x1920", watermark: "removed", created: "2024-01-14T14:31:00Z" },
  { id: "img-012", asin: "B0GLGBDVJY", slot: 4, title: "Craft Story", url: "/placeholder-12.jpg", size: 2580000, dimensions: "1600x1920", watermark: "clean", created: "2024-01-14T14:34:00Z" },
];

const watermarkStatusConfig = {
  clean: { label: "Clean", variant: "success" as const },
  removed: { label: "Removed", variant: "warning" as const },
  detected: { label: "Detected", variant: "error" as const },
  pending: { label: "Pending", variant: "neutral" as const },
};

export default function ImagesPage() {
  return (
    <MainLayout title="Images" subtitle="Browse and manage generated product images">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="heading-md font-semibold">Generated Images</h2>
            <p className="text-body-sm text-surface-500">Browse, download, and manage generated product images</p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline"><Download className="w-4 h-4 mr-2" /> Download All</Button>
            <Button variant="primary"><Upload className="w-4 h-4 mr-2" /> Upload Images</Button>
          </div>
        </div>

        <Card className="mb-6">
          <CardContent className="p-4">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="relative sm:col-span-2">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" aria-hidden="true" />
                <Input placeholder="Search by ASIN, slot, title..." className="pl-10" />
              </div>
              <select className="input" defaultValue="">
                <option value="">All ASINs</option>
                <option value="B0D44XVV2F">B0D44XVV2F - Chikankari Kurta</option>
                <option value="B0GLGBDVJY">B0GLGBDVJY - Cotton Kurta Set</option>
              </select>
              <select className="input" defaultValue="">
                <option value="">All slots</option>
                <option value="1">Slot 1 - Hero</option>
                <option value="2">Slot 2 - Back</option>
                <option value="3">Slot 3 - Side</option>
                <option value="4">Slot 4 - Craft</option>
                <option value="5">Slot 5 - Lifestyle</option>
                <option value="6">Slot 6 - Styling</option>
                <option value="7">Slot 7 - USP</option>
                <option value="8">Slot 8 - Guide</option>
              </select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-4">
              {images.map((img) => (
                <div key={img.id} className="group relative bg-white rounded-lg border border-surface-200 overflow-hidden hover:shadow-lg transition-shadow">
                  <div className="aspect-[1600/1920] bg-surface-100 relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-surface-200 to-surface-300 flex items-center justify-center">
                      <Sparkles className="w-12 h-12 text-surface-400" />
                    </div>
                    <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="p-2 bg-white/90 rounded-lg hover:bg-surface-100" aria-label="View fullscreen"><Maximize className="w-4 h-4" /></button>
                      <button className="p-2 bg-white/90 rounded-lg hover:bg-surface-100" aria-label="Download"><Download className="w-4 h-4" /></button>
                      <button className="p-2 bg-white/90 rounded-lg hover:bg-surface-100" aria-label="More"><MoreHorizontal className="w-4 h-4" /></button>
                    </div>
                    {img.watermark !== "clean" && (
                      <span className="absolute bottom-2 left-2 px-2 py-1 bg-warning-500/90 text-white text-xs rounded">Removed</Badge>
                    )}
                  </div>
                  <div className="p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 bg-info-50 text-info-700 text-caption rounded-full">Slot {img.slot}</Badge>
                      <span className="px-2 py-0.5 bg-surface-100 text-surface-700 text-caption rounded-full">{img.dimensions}</Badge>
                    </div>
                    <p className="font-medium text-surface-900 truncate">{img.title}</p>
                    <p className="text-body-sm text-surface-500 truncate">ASIN: {img.asin}</p>
                    <div className="flex items-center justify-between text-caption text-surface-500 pt-2 border-t border-surface-100">
                      <span>{(img.size / 1024 / 1024).toFixed(2)} MB</span>
                      <span>{new Date(img.created).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-between">
          <p className="text-body-sm text-surface-500">Showing 1 to 12 of 45 images</p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled><ChevronLeft className="w-4 h-4" /></Button>
            <button className="px-3 py-1.5 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">1</button>
            <button className="px-3 py-1.5 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">2</button>
            <button className="px-3 py-1.5 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">3</button>
            <button className="px-3 py-1.5 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">4</button>
            <button className="px-3 py-1.5 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">5</button>
            <button className="px-3 py-1.5 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">6</button>
            <button className="px-3 py-1.5 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">7</button>
            <button className="px-3 py-1.5 border border-surface-300 rounded-lg text-body-sm hover:bg-surface-50">8</button>
            <Button variant="outline" size="sm"><ChevronRight className="w-4 h-4" /></Button>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

import { Select } from "@/components/ui/Dropdown";