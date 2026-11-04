"use client";

import { useState, type ReactNode } from "react";
import { Menu, Sun, Moon, Bell, User, LogOut, Settings, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Avatar } from "@/components/ui/Avatar";
import { Dropdown } from "@/components/ui/Dropdown";
import { Tooltip } from "@/components/ui/Tooltip";

interface HeaderProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function Header({ title, subtitle, actions }: HeaderProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);

  const userMenuItems = [
    { key: "profile", label: "Profile", icon: <User className="w-4 h-4" /> },
    { key: "settings", label: "Settings", icon: <Settings className="w-4 h-4" /> },
    { key: "divider", divider: true },
    { key: "logout", label: "Sign out", icon: <LogOut className="w-4 h-4" />, danger: true },
  ];

  const notifications = [
    { id: "1", title: "Generation completed", message: "ASIN B0D44XVV2F - All 8 slots generated", time: "5m ago", read: false },
    { id: "2", title: "Watermark removed", message: "3 images cleaned for ASIN B0GLGBDVJY", time: "1h ago", read: false },
    { id: "3", title: "Job failed", message: "ASIN B0CP9MK37V - Slot 3 generation failed", time: "3h ago", read: true },
  ];

  return (
    <header className="sticky top-0 z-sticky bg-white/80 backdrop-blur-lg border-b border-surface-200">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Mobile menu toggle */}
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label="Toggle menu"
        >
          <Menu className="w-5 h-5" />
        </Button>

        {/* Title section */}
        <div className="flex-1 min-w-0 lg:hidden">
          {title && <h1 className="heading-sm font-semibold text-surface-900 truncate">{title}</h1>}
          {subtitle && <p className="text-body-sm text-surface-500 truncate">{subtitle}</p>}
        </div>

        {/* Center title on desktop */}
        <div className="hidden lg:flex lg:flex-1 lg:items-center lg:justify-center">
          {title && <h1 className="heading-lg font-semibold text-surface-900">{title}</h1>}
        </div>

        {/* Right side actions */}
        <div className="flex items-center gap-2 lg:gap-4">
          {actions}

          {/* Theme toggle */}
          <Tooltip content={darkMode ? "Light mode" : "Dark mode"}>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDarkMode(!darkMode)}
              aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
            >
              {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </Button>
          </Tooltip>

          {/* Notifications */}
          <Tooltip content="Notifications">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              aria-label="Notifications"
              aria-expanded={notificationsOpen}
            >
              <Bell className="w-5 h-5 relative" />
              {notifications.some((n) => !n.read) && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-error-500 text-white text-[0.5rem] font-medium rounded-full flex items-center justify-center">
                  {notifications.filter((n) => !n.read).length}
                </span>
              )}
            </Button>
          </Tooltip>

          {/* User menu */}
          <Tooltip content="User menu">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              aria-label="User menu"
              aria-expanded={userMenuOpen}
              className="p-1"
            >
              <Avatar src="/api/placeholder/32/32" name="User" size="sm" />
              <ChevronDown className="w-4 h-4 ml-1" />
            </Button>
          </Tooltip>

          {/* Dropdowns */}
          <Dropdown
            items={userMenuItems}
            onSelect={(key) => {
              setUserMenuOpen(false);
              if (key === "logout") {
                // Handle logout
              }
            }}
            align="right"
          >
            <Button variant="ghost" size="icon" className="p-1" aria-label="User menu" aria-expanded={userMenuOpen}>
              <Avatar name="User" size="sm" />
              <ChevronDown className="w-4 h-4 ml-1" />
            </Button>
          </Dropdown>

          <Dropdown
            items={notifications.map((n) => ({
              key: n.id,
              label: `${n.title}${n.read ? "" : " • New"}`,
              disabled: false,
            }))}
            onSelect={(id) => {
              setNotificationsOpen(false);
              // Mark as read
            })}
            align="right"
          >
            <Tooltip content="Notifications">
              <Button variant="ghost" size="icon" aria-label="Notifications">
                <Bell className="w-5 h-5 relative" />
                {notifications.some((n) => !n.read) && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-error-500 text-white text-[0.5rem] font-medium rounded-full flex items-center justify-center">
                    {notifications.filter((n) => !n.read).length}
                  </span>
                )}
              </Button>
            </Tooltip>
          </Dropdown>
        </div>
      </div>
    </header>
  );
}