"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: React.ReactNode;
  iconColor?: "brand" | "success" | "warning" | "error" | "info";
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function MetricCard({
  title,
  value,
  change,
  changeLabel,
  icon,
  iconColor = "brand",
  trend,
  className,
}: MetricCardProps) {
  const iconColors = {
    brand: "bg-brand-50 text-brand-600",
    success: "bg-success-50 text-success-600",
    warning: "bg-warning-50 text-warning-600",
    error: "bg-error-50 text-error-600",
    info: "bg-info-50 text-info-600",
  };

  const trendIcons = {
    up: <TrendingUp className="w-4 h-4 text-success-600" aria-hidden="true" />,
    down: <TrendingDown className="w-4 h-4 text-error-600" aria-hidden="true" />,
    neutral: <Minus className="w-4 h-4 text-surface-500" aria-hidden="true" />,
  };

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-body-sm text-surface-500">{title}</p>
          <p className="heading-lg font-semibold text-surface-900 mt-1">{value}</p>
          {change !== undefined && (
            <div className="flex items-center gap-1 mt-2">
              {trendIcons[trend ?? (change > 0 ? "up" : change < 0 ? "down" : "neutral")]}
              <span className={cn(
                "text-body-sm font-medium",
                change > 0 ? "text-success-600" : change < 0 ? "text-error-600" : "text-surface-500"
              )}>
                {change > 0 ? "+" : ""}{change.toFixed(1)}%
              </span>
              {changeLabel && <span className="text-body-sm text-surface-500">{changeLabel}</span>}
            </div>
          )}
        </div>
        <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", icon ? "" : "hidden")}>
          {icon}
        </div>
      </div>
    </div>
  );
}

export { MetricCard };