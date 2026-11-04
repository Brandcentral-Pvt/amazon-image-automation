"use client";

import { useState, useRef, useEffect, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  position?: "top" | "bottom" | "left" | "right";
  delay?: number;
  className?: string;
}

export function Tooltip({
  content,
  children,
  position = "top",
  delay = 200,
  className,
}: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout>();
  const childRef = useRef<HTMLElement>(null);

  const show = () => {
    timeoutRef.current = setTimeout(() => setVisible(true), delay);
  };

  const hide = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setVisible(false);
  };

  const handleMouseEnter = () => {
    if (!children.props.disabled) show();
  };

  const handleMouseLeave = () => hide();
  const handleFocus = () => show();
  const handleBlur = () => hide();

  const positionStyles = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  const arrowStyles = {
    top: "top-full left-1/2 -translate-x-1/2 border-t-surface-900",
    bottom: "bottom-full left-1/2 -translate-x-1/2 border-b-surface-900",
    left: "left-full top-1/2 -translate-y-1/2 border-l-surface-900",
    right: "right-full top-1/2 -translate-y-1/2 border-r-surface-900",
  };

  const clonedChild = React.cloneElement(children, {
    ref: childRef,
    onMouseEnter: handleMouseEnter,
    onMouseLeave: handleMouseLeave,
    onFocus: handleFocus,
    onBlur: handleBlur,
  });

  return (
    <div className="relative inline-block" onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}>
      {clonedChild}
      {visible && (
        <div
          className={cn(
            "tooltip",
            positionStyles[position],
            "z-tooltip"
          )}
          role="tooltip"
        >
          <div className="flex items-center gap-1">{content}</div>
          <div
            className={cn(
              "absolute w-0 h-0 border-4 border-transparent",
              arrowStyles[position]
            )}
            aria-hidden="true"
          />
        </div>
      )}
    </div>
  );
}

export { Tooltip };