"use client";

import { useRef, useEffect, type ReactNode, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface ScrollAreaProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  horizontal?: boolean;
  vertical?: boolean;
}

export function ScrollArea({
  className,
  children,
  horizontal = false,
  vertical = true,
  ...props
}: ScrollAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const style = window.getComputedStyle(el);
    const hasHorizontalScroll = el.scrollWidth > el.clientWidth;
    const hasVerticalScroll = el.scrollHeight > el.clientHeight;

    if (horizontal && hasHorizontalScroll) {
      el.style.scrollbarWidth = "thin";
      el.style.scrollbarColor = "rgb(163 163 163) transparent";
    }
    if (vertical && hasVerticalScroll) {
      el.style.scrollbarWidth = "thin";
      el.style.scrollbarColor = "rgb(163 163 163) transparent";
    }
  }, [horizontal, vertical]);

  return (
    <div
      ref={scrollRef}
      className={cn(
        "scrollbar-hide",
        horizontal && "overflow-x-auto",
        vertical && "overflow-y-auto",
        "flex-1"
      )}
      {...props}
    >
      <div className={cn(horizontal && "flex", vertical && "min-h-0")}>{children}</div>
    </div>
  );
}

export { ScrollArea };