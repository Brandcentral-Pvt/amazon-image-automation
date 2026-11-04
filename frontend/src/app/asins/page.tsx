"use client";

import { MainLayout } from "@/components/layout";
import { Table } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Dropdown } from "@/components/ui/Dropdown";
import { Upload, Download, Search, Filter, MoreHorizontal, Eye, Edit, Trash2, Download as DownloadIcon, FileText } from "lucide-react";
import { formatRelativeTime, formatNumber } from "@/lib/utils";

const allASINs = [
  { asin: "B0D44XVV2F", title: "BHARVITA Women's Cotton Embroidered Chikankari", brand: "BHARVITA", category: "Women's Clothing", price: "$29.99", images: 12, status: "completed", created: "2024-01-15T10:30:00Z" },
  { asin: "B0GLGBDVJY", title: "Amayra Women's Pure Cotton A-Line Kurta Set", brand: "Amayra", category: "Women's Clothing", price: "$34.99", images: 5, status: "completed", created: "2024-01-14T14:22:00Z" },
  { asin: "B0CP9MK37V", title: "ROYALICA Chinon Silk Sequence Zari Anarkali", brand: "ROYALICA", category: "Women's Clothing", price: "$49.99", images: 5, status: "generating", created: "2024-01-13T09:15:00Z" },
  { asin: "B0B4PZMWVG", title: "ROYALICA Women's Georgette Floral Embroidered", brand: "ROYALICA", category: "Women's Clothing", price: "$39.99", images: 11, status: "queued", created: "2024-01-12T16:45:00Z" },
  { asin: "B0CZRF18MK", title: "ROYALICA Women's Trousers", brand: "ROYALICA", category: "Women's Clothing", price: "$24.99", images: 10, status: "failed", created: "2024-01-11T11:20:00Z" },
  { asin: "B0CK4HX5RS", title: "ROYALICA Women's Vichitra Silk Blend Kurta", brand: "ROYALICA", category: "Women's Clothing", price: "$44.99", images: 5, status: "completed", created: "2024-01-10T08:30:00Z" },
  { asin: "B0CLRPLR4D", title: "ROYALICA Women Regular Fit Self Design Casual Shirt", brand: "ROYALICA", category: "Women's Clothing", price: "$22.99", images: 5, status: "generating", created: "2024-01-09T13:45:00Z" },
  { asin: "B0CGNJ927C", title: "ROYALICA Boy's Cotton Solid Regular Mens Kurta", brand: "ROYALICA", category: "Men's Clothing", price: "$19.99", images: 5, status: "completed", created: "2024-01-08T10:00:00Z" },
];

const statusConfig = {
  completed: { label: "Completed", variant: "success" as const },
  generating: { label: "Generating", variant: "info" as const },
  queued: { label: "Queued", variant: "warning" as const },
  failed: { label: "Failed", variant: "error" as const },
  scraped: { label: "Scraped", variant: "neutral" as const },
  pending: { label: "Pending", variant: "neutral" as const },
};

export default function ASINsPage() {
  return (
    <MainLayout title="ASINs" subtitle="Manage your Amazon product listings">
      <div className="space-y-6">
        {/* Header Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="heading-md font-semibold">All ASINs</h2>
            <p className="text-body-sm text-surface-500">Manage and track your Amazon product listings</p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" className="flex-1 sm:flex-none">
              <FileText className="w-4 h-4 mr-2" />
              Export CSV
            </Button>
            <Button variant="primary">
              <Upload className="w-4 h-4 mr-2" />
              Add ASINs
            </Button>
          </div>
        </div>

        {/* Search & Filters */}
        <Card className="mb-6">
          <CardContent className="p-4">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="relative sm:col-span-2">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" aria-hidden="true" />
                <Input
                  placeholder="Search ASINs, titles, brands..."
                  className="pl-10"
                  onChange={(e) => console.log("Search:", e.target.value)}
                />
              </div>
              <Select
                placeholder="All statuses"
                options={[
                  { value: "", label: "All statuses" },
                  { value: "completed", label: "Completed" },
                  { value: "generating", label: "Generating" },
                  { value: "queued", label: "Queued" },
                  { value: "failed", label: "Failed" },
                  { value: "scraped", label: "Scraped" },
                  { value: "pending", label: "Pending" },
                ]}
                onChange={(v) => console.log("Status filter:", v)}
              />
              <Select
                placeholder="All categories"
                options={[
                  { value: "", label: "All categories" },
                  { value: "women", label: "Women's Clothing" },
                  { value: "men", label: "Men's Clothing" },
                  { value: "kids", label: "Kids' Clothing" },
                  { value: "accessories", label: "Accessories" },
                ]}
                onChange={(v) => console.log("Category filter:", v)}
              />
            </div>
          </CardContent>
        </Card>

        {/* ASINs Table */}
        <Card>
          <CardContent className="p-0">
            <Table
              columns={[
                { key: "select", header: "", accessor: () => <input type="checkbox" className="w-4 h-4" />, width: "40px" },
                { key: "asin", header: "ASIN", accessor: "asin", width: "130px" },
                { key: "title", header: "Product Title", accessor: (row) => (
                  <div className="max-w-xs">
                    <p className="font-medium text-surface-900 truncate">{row.title}</p>
                    <p className="text-body-sm text-surface-500 truncate">{row.brand} • {row.category}</p>
                  </div>
                ) },
                { key: "category", header: "Category", accessor: "category", width: "140px" },
                { key: "price", header: "Price", accessor: "price", width: "100px" },
                { key: "images", header: "Images", accessor: "images", width: "80px", render: (val) => (
                  <span className="font-mono text-body-sm">{val} images</span>
                ) },
                { key: "status", header: "Status", accessor: "status", width: "130px", render: (val) => {
                  const config = statusConfig[val as keyof typeof statusConfig] || { label: val, variant: "neutral" as const };
                  return <Badge variant={config.variant} size="sm">{config.label}</Badge>;
                }},
                { key: "created", header: "Date Added", accessor: (row) => formatRelativeTime(row.created), width: "140px" },
                { key: "actions", header: "Actions", accessor: (row) => (
                  <Dropdown
                    items={[
                      { key: "view", label: "View details", icon: <Eye className="w-4 h-4" /> },
                      { key: "edit", label: "Edit", icon: <Edit className="w-4 h-4" /> },
                      { key: "scrape", label: "Re-scrape", icon: <RefreshCw className="w-4 h-4" /> },
                      { key: "generate", label: "Generate images", icon: <Zap className="w-4 h-4" /> },
                      { key: "divider", divider: true },
                      { key: "download", label: "Download images", icon: <DownloadIcon className="w-4 h-4" /> },
                      { key: "delete", label: "Delete", icon: <Trash2 className="w-4 h-4" />, danger: true },
                    ]}
                    onSelect={(key) => console.log("Action:", key, row.asin)}
                  >
                    <Button variant="ghost" size="icon" aria-label="More actions">
                      <MoreHorizontal className="w-4 h-4" />
                    </Button>
                  </Dropdown>
                ), width: "80px" },
              ]}
              data={allASINs}
              keyExtractor={(row) => row.asin}
              striped
              hoverable
              emptyMessage="No ASINs found. Add your first ASIN to get started."
            />
          </CardContent>
        </Card>

        {/* Pagination */}
        <div className="flex items-center justify-between">
          <p className="text-body-sm text-surface-500">Showing 1 to 8 of 24 ASINs</p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled><ChevronLeft className="w-4 h-4" /></Button>
            <Button variant="outline" size="sm">1</Button>
            <Button variant="outline" size="sm">2</Button>
            <Button variant="outline" size="sm">3</Button>
            <Button variant="outline" size="sm"><ChevronRight className="w-4 h-4" /></Button>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

// Need to import Select and Dropdown
import { Select } from "@/components/ui/Dropdown";
import { Dropdown } from "@/components/ui/Dropdown";
import { ChevronDown } from "lucide-react";