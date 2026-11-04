"use client";

import { type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "text" | "circular" | "rectangular" | "card";
  width?: string | number;
  height?: string | number;
  lines?: number;
}

export function Skeleton({
  className,
  variant = "text",
  width,
  height,
  lines = 3,
  ...props
}: SkeletonProps) {
  const variantStyles = {
    text: "h-4 w-full",
    circular: "rounded-full",
    rectangular: "rounded-lg",
    card: "rounded-xl",
  };

  const contentStyles = {
    text: "space-y-3",
    circular: "",
    rectangular: "",
    card: "space-y-4",
  };

  if (variant === "text") {
    return (
      <div className={cn("space-y-3", className)} {...props}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={cn("skeleton h-4 rounded", i === lines - 1 && "w-3/4")}
            style={{ width: i === lines - 1 ? "60%" : "100%" }}
          />
        ))}
      </div>
    );
  }

  if (variant === "circular") {
    return (
      <div
        className={cn("skeleton rounded-full", className)}
        style={{ width, height: height || width }}
        {...props}
      />
    );
  }

  if (variant === "rectangular") {
    return (
      <div
        className={cn("skeleton rounded-lg", className)}
        style={{ width: width || "100%", height: height || "100%" }}
        {...props}
      />
    );
  }

  // Card variant - simulates a card with image, title, and text
  return (
    <div className={cn("skeleton card space-y-4 p-6", className)} {...props}>
      <div className="skeleton h-40 w-full rounded-lg" />
      <div className="space-y-3">
        <div className="skeleton h-6 w-3/4 rounded" />
        <div className="skeleton h-4 w-1/2 rounded" />
        <div className="skeleton h-4 w-full rounded" />
      </div>
      <div className="flex gap-2">
        <div className="skeleton h-8 w-20 rounded-full" />
        <div className="skeleton h-8 w-24 rounded-full" />
      </div>
    </div>
  );
}

export interface SkeletonTableProps {
  rows?: number;
  columns?: number;
  className?: string;
}

export function SkeletonTable({ rows = 5, columns = 4, className }: SkeletonTableProps) {
  return (
    <div className={cn("table-container", className)}>
      <table className="table">
        <thead>
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="px-4 py-3">
                <div className="skeleton h-4 w-20 rounded" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr key={rowIndex}>
              {Array.from({ length: columns }).map((_, colIndex) => (
                <td key={colIndex} className="px-4 py-3">
                  <div className="skeleton h-4 w-24 rounded" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export interface SkeletonCardProps {
  className?: string;
  hasImage?: boolean;
  lines?: number;
}

export function SkeletonCard({ className, hasImage = true, lines = 3 }: SkeletonCardProps) {
  return (
    <div className={cn("skeleton card p-6 space-y-4", className)}>
      {hasImage && <div className="skeleton h-40 w-full rounded-lg" />}
      <div className="space-y-3">
        <div className="skeleton h-6 w-3/4 rounded" />
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="skeleton h-4 rounded" style={{ width: i === lines - 1 ? "60%" : "100%" }} />
        ))}
      </div>
      <div className="flex gap-2 pt-2">
        <div className="skeleton h-8 w-20 rounded-full" />
        <div className="skeleton h-8 w-24 rounded-full" />
      </div>
    </div>
  );
}

export { Skeleton, SkeletonTable, SkeletonCard };