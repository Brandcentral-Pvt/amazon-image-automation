"use client";

import { useState, type ReactNode } from "react";
import { ChevronRight, ChevronLeft, Home, Database, Zap, Image, Settings, HelpCircle, FolderOpen, Trash2, Clock, CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { useRouter, usePathname } from "next/navigation";

interface NavItem {
  key: string;
  label: string;
  icon: React.ReactNode;
  href: string;
  badge?: string | number;
  badgeVariant?: "success" | "warning" | "error" | "info" | "neutral" | "brand";
  children?: NavItem[];
  disabled?: boolean;
}

const navigation: NavItem[] = [
  {
    key: "dashboard",
    label: "Dashboard",
    icon: <Home className="w-5 h-5" />,
    href: "/dashboard",
  },
  {
    key: "asins",
    label: "ASINs",
    icon: <Database className="w-5 h-5" />,
    href: "/asins",
    badge: 24,
    badgeVariant: "info",
  },
  {
    key: "generation",
    label: "Generation",
    icon: <Zap className="w-5 h-5" />,
    href: "/generation",
    children: [
      { key: "queue", label: "Queue", icon: <Clock className="w-4 h-4" }, href: "/generation/queue" },
      { key: "history", label: "History", icon: <CheckCircle className="w-4 h-4" }, href: "/generation/history" },
      { key: "failed", label: "Failed", icon: <AlertCircle className="w-4 h-4" }, href: "/generation/failed" },
    ],
  },
  {
    key: "images",
    label: "Images",
    icon: <Image className="w-5 h-5" />,
    href: "/images",
    badge: 156,
    badgeVariant: "success",
  },
  {
    key: "watermark",
    label: "Watermark",
    icon: <Zap className="w-5 h-5" />,
    href: "/watermark",
  },
  {
    key: "settings",
    label: "Settings",
    icon: <Settings className="w-5 h-5" />,
    href: "/settings",
  },
  {
    key: "help",
    label: "Help & Docs",
    icon: <HelpCircle className="w-5 h-5" />,
    href: "/help",
  },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  user?: { name: string; email: string; avatar?: string };
}

export function Sidebar({ open, onClose, user }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const router = useRouter();
  const pathname = usePathname();

  const toggleItem = (key: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  const renderItem = (item: NavItem, level = 0) => {
    const active = isActive(item.href);
    const hasChildren = item.children && item.children.length > 0;
    const expanded = expandedItems.has(item.key);

    const handleClick = (e: React.MouseEvent) => {
      e.preventDefault();
      if (hasChildren) {
        toggleItem(item.key);
      } else if (item.href) {
        router.push(item.href);
        if (window.innerWidth < 1024) onClose();
      }
    };

    return (
      <div key={item.key}>
        <button
          onClick={handleClick}
          disabled={item.disabled}
          className={cn(
            "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors",
            "text-left",
            active && !hasChildren ? "bg-brand-50 text-brand-700" : "text-surface-600 hover:bg-surface-50 hover:text-surface-900",
            item.disabled && "opacity-50 cursor-not-allowed",
            level > 0 && "pl-8"
          )}
          aria-expanded={hasChildren ? expanded : undefined}
          aria-current={active ? "page" : undefined}
        >
          <span className="flex-shrink-0 w-5 h-5" aria-hidden="true">{item.icon}</span>
          {!collapsed && <span className="flex-1 text-body-sm font-medium">{item.label}</span>}
          {item.badge && !collapsed && (
            <Badge variant={item.badgeVariant || "neutral"} size="sm">{item.badge}</Badge>
          )}
          {hasChildren && !collapsed && (
            <ChevronRight
              className={cn("w-4 h-4 flex-shrink-0 ml-auto transition-transform", expanded && "rotate-90")}
              aria-hidden="true"
            />
          )}
        </button>
        {hasChildren && !collapsed && expanded && (
          <div className="mt-1 space-y-1" role="group" aria-label={`${item.label} submenu`}>
            {item.children?.map((child) => renderItem(child, level + 1))}
          )}
        </div>
      </>
    );
  };

  return (
    <>
      {/* Overlay for mobile */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-[59] lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed top-0 left-0 z-[60] h-full bg-white border-r border-surface-200 transition-all duration-300 ease-out",
          open ? "translate-x-0" : "-translate-x-full",
          collapsed ? "w-16" : "w-64",
          "lg:translate-x-0 lg:z-[50]"
        )}
        aria-label="Main navigation"
      >
        {/* Logo / Brand */}
        <div className={cn("flex items-center gap-3 p-4 border-b border-surface-200", collapsed && "justify-center")}>
          {!collapsed && (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" aria-hidden="true" />
              </div>
              <div>
                <p className="heading-sm font-semibold text-surface-900">AmzImage</p>
                <p className="text-caption text-surface-500">Automation</p>
              </div>
            </div>
          )}
          {collapsed && (
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center mx-auto">
              <Zap className="w-5 h-5 text-white" aria-hidden="true" />
            </div>
          )}

          {/* Collapse toggle */}
          <Button
            variant="ghost"
            size="icon"
            className={cn("ml-auto", collapsed && "ml-0 mx-auto")}
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
          >
            {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1" aria-label="Main navigation">
          {navigation.map((item) => renderItem(item))}
        </nav>

        {/* User section */}
        <div className={cn("p-4 border-t border-surface-200", collapsed && "justify-center")}>
          {!collapsed && user && (
            <div className="flex items-center gap-3">
              <Avatar src={user.avatar} name={user.name} size="sm" />
              <div className="flex-1 min-w-0">
                <p className="text-body-sm font-medium text-surface-900 truncate">{user.name}</p>
                <p className="text-caption text-surface-500 truncate">{user.email}</p>
              </div>
            </div>
          )}
          {collapsed && (
            <Avatar name="User" size="sm" className="mx-auto" />
          )}
        </div>
      </nav>
    </aside>
  );
}

export { Sidebar };