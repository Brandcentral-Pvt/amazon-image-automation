"use client";

import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface TabItem {
  key: string;
  label: string;
  icon?: ReactNode;
  disabled?: boolean;
  count?: number;
}

interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (key: string) => void;
  variant?: "default" | "pills" | "underline";
  className?: string;
}

export function Tabs({ tabs, activeTab, onChange, variant = "underline", className }: TabsProps) {
  return (
    <div className={cn(className)}>
      <div
        className={cn(
          "tabs",
          variant === "pills" && "bg-surface-100 p-1 rounded-lg border-none",
          variant === "underline" && "border-b border-surface-200"
        )}
        role="tablist"
        aria-label="Tabs"
      >
        {tabs.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            aria-disabled={tab.disabled}
            onClick={() => !tab.disabled && onChange(tab.key)}
            disabled={tab.disabled}
            className={cn(
              "tab",
              variant === "pills" &&
                "rounded-md border-transparent py-2 px-3 transition-all",
              activeTab === tab.key &&
                (variant === "pills"
                  ? "bg-white text-brand-600 shadow-sm"
                  : "text-brand-500 border-brand-500"),
              tab.disabled && "opacity-50 cursor-not-allowed"
            )}
          >
            {tab.icon && <span className="flex-shrink-0 mr-2">{tab.icon}</span>}
            {tab.label}
            {tab.count !== undefined && (
              <span
                className={cn(
                  "ml-2 px-1.5 py-0.5 text-[0.625rem] font-medium rounded-full",
                  activeTab === tab.key
                    ? "bg-brand-100 text-brand-700"
                    : "bg-surface-100 text-surface-500"
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

interface TabPanelProps {
  active: boolean;
  children: React.ReactNode;
  className?: string;
}

export function TabPanel({ active, children, className }: TabPanelProps) {
  if (!active) return null;
  return <div className={cn("animate-fade-in", className)}>{children}</div>;
}

export { Tabs, TabPanel };