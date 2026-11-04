"use client";

import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "success" | "warning" | "error" | "info" | "neutral" | "brand";
  size?: "sm" | "md" | "lg";
  dot?: boolean;
  icon?: React.ReactNode;
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = "neutral", size = "md", dot = false, icon, children, ...props }, ref) => {
    const variantStyles = {
      success: "badge-success",
      warning: "badge-warning",
      error: "badge-error",
      info: "badge-info",
      neutral: "badge-neutral",
      brand: "badge-brand",
    };
    const sizeStyles = {
      sm: "px-1.5 py-0.5 text-[0.625rem]",
      md: "px-2 py-0.5 text-caption",
      lg: "px-2.5 py-1 text-body-sm",
    };

    return (
      <span
        ref={ref}
        className={cn("badge", variantStyles[variant], sizeStyles[size], "gap-1.5", className)}
        {...props}
      >
        {props.dot && <span className="w-1.5 h-1.5 rounded-full bg-current" aria-hidden="true" />}
        {props.icon}
        {children}
      </span>
    );
  }
);

Badge.displayName = "Badge";

export { Badge as default };