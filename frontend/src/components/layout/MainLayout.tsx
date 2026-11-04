"use client";

import { type ReactNode, useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { ScrollArea } from "@/components/ui/ScrollArea";

interface MainLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  headerActions?: React.ReactNode;
}

export function MainLayout({ children, title, subtitle, headerActions }: MainLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [mobile, setMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setMobile(window.innerWidth < 1024);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  return (
    <div className="min-h-screen bg-surface-50">
      {/* Mobile sidebar */}
      {mobile && (
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      )}

      {/* Desktop sidebar */}
      {!mobile && <Sidebar open={true} onClose={() => {}} />}

      {/* Main content */}
      <div
        className={cn(
          "min-h-screen transition-all duration-300",
          mobile ? "lg:ml-0" : "lg:ml-64"
        )}
      >
        {/* Header */}
        <Header
          title={title}
          subtitle={subtitle}
          actions={headerActions}
        />

        {/* Content */}
        <main className="p-4 sm:p-6 lg:p-8">
          <ScrollArea className="h-[calc(100vh-4rem)] lg:h-[calc(100vh-4rem)]">
            <div className="max-w-full">{children}</div>
          </ScrollArea>
        </main>
      </div>
    </div>
  );
}

export { MainLayout };