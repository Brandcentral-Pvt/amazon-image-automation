"use client";

import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  showLabel?: boolean;
  label?: string;
  size?: "sm" | "md" | "lg";
  variant?: "default" | "success" | "warning" | "error";
  animated?: boolean;
}

export function Progress({
  className,
  value,
  max = 100,
  showLabel = false,
  label,
  size = "md",
  variant = "default",
  animated = false,
  ...props
}: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  const sizeStyles = {
    sm: "h-1",
    md: "h-2",
    lg: "h-3",
  };

  const variantStyles = {
    default: "bg-brand-500",
    success: "bg-success-500",
    warning: "bg-warning-500",
    error: "bg-error-500",
  };

  return (
    <div className={cn("w-full", className)} {...props}>
      {(showLabel || label) && (
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-body-sm font-medium text-surface-700">{label ?? `${Math.round(percentage)}%`}</span>
          {showLabel && <span className="text-body-sm text-surface-500">{Math.round(percentage)}%</span>}
        </div>
      )}
      <div
        className={cn(
          "progress",
          sizeStyles[size],
          animated && "animate-pulse"
        )}
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={cn("progress-bar", variantStyles[variant])}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export interface CircularProgressProps extends HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  size?: number;
  strokeWidth?: number;
  showLabel?: boolean;
  label?: string;
  variant?: "default" | "success" | "warning" | "error";
}

export function CircularProgress({
  className,
  value,
  max = 100,
  size = 64,
  strokeWidth = 4,
  showLabel = false,
  label,
  variant = "default",
  ...props
}: CircularProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - percentage / 100);

  const variantStyles = {
    default: "text-brand-500",
    success: "text-success-500",
    warning: "text-warning-500",
    error: "text-error-500",
  };

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} {...props}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          className="text-surface-200 dark:text-surface-700"
          strokeWidth={strokeWidth}
          stroke="currentColor"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          className={cn("transition-all duration-500 ease-out", variantStyles[variant])}
          strokeWidth={strokeWidth}
          stroke="currentColor"
          strokeLinecap="round"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transformOrigin: "center" }}
        />
      </svg>
      {(showLabel || label) && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-body-sm font-medium text-surface-900">
            {label ?? `${Math.round(percentage)}%`}
          </span>
        </div>
      )}
    </div>
  );
}

export interface StepProgressProps {
  steps: Array<{ label: string; description?: string; completed?: boolean; current?: boolean }>;
  className?: string;
}

export function StepProgress({ steps, className }: StepProgressProps) {
  return (
    <div className={cn("relative", className)}>
      <div className="absolute left-[14px] top-0 bottom-0 w-0.5 bg-surface-200" aria-hidden="true" />
      <div className="space-y-6">
        {steps.map((step, index) => (
          <div key={index} className="relative flex gap-4">
            <div className="relative flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full border-2 transition-all duration-300">
              {step.completed ? (
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : step.current ? (
                <span className="relative w-2.5 h-2.5 rounded-full animate-pulse-soft" aria-hidden="true" />
              ) : (
                <span className="text-caption font-medium text-surface-400">{index + 1}</span>
              )}
            </div>
            <div className="flex-1 min-w-0 pt-1">
              <p className={cn("font-medium text-body-sm", step.completed ? "text-surface-600" : step.current ? "text-surface-900" : "text-surface-400")}>
                {step.label}
              </p>
              {step.description && (
                <p className="text-body-sm text-surface-500 mt-0.5">{step.description}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export { Progress, CircularProgress, StepProgress };