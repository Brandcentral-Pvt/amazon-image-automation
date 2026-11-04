"use client";

import { useState, useRef, useEffect, type ReactNode } from "react";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./Button";

export interface DropdownItem {
  key: string;
  label: string;
  icon?: ReactNode;
  disabled?: boolean;
  danger?: boolean;
  divider?: boolean;
}

interface DropdownProps {
  trigger: ReactNode;
  items: DropdownItem[];
  onSelect: (key: string) => void;
  align?: "left" | "right";
  offset?: number;
}

export function Dropdown({ trigger, items, onSelect, align = "right", offset = 4 }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }

    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    if (open) {
      document.addEventListener("keydown", handleEscape);
    }
    return () => document.removeEventListener("keydown", handleEscape);
  }, [open]);

  return (
    <div className="relative inline-block" ref={triggerRef}>
      <div>{trigger}</div>
      {open && (
        <div
          ref={dropdownRef}
          className={cn(
            "dropdown",
            align === "right" ? "right-0" : "left-0"
          )}
          style={{ marginTop: offset }}
          role="menu"
        >
          {items.map((item, index) => {
            if (item.divider) {
              return <div key={`divider-${index}`} className="dropdown-divider" role="separator" />;
            }
            return (
              <button
                key={item.key}
                onClick={() => {
                  if (!item.disabled) {
                    onSelect(item.key);
                    setOpen(false);
                  }
                }}
                disabled={item.disabled}
                className={cn(
                  "dropdown-item w-full text-left",
                  item.danger && "text-error-500 hover:bg-error-50",
                  item.disabled && "opacity-50 cursor-not-allowed"
                )}
                role="menuitem"
                aria-disabled={item.disabled}
              >
                {item.icon && <span className="w-5 h-5 flex-shrink-0">{item.icon}</span>}
                <span className="flex-1">{item.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  label?: string;
  hint?: string;
  error?: string;
  disabled?: boolean;
}

export function Select({
  value,
  onChange,
  options,
  placeholder,
  label,
  hint,
  error,
  disabled,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const selectRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const selectedOption = options.find((opt) => opt.value === value);

  return (
    <div className="w-full" ref={selectRef}>
      {label && <label className="label">{label}</label>}
      <div className="relative">
        <Button
          ref={(el) => (selectRef.current = el as unknown as HTMLDivElement)}
          variant="outline"
          className={cn("w-full justify-between", error && "border-error-500")}
          onClick={() => !disabled && setOpen(!open)}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className={cn("truncate flex-1", !value && "text-surface-400")}>
            {value ? selectedOption?.label : placeholder}
          </span>
          <ChevronDown className={cn("w-4 h-4 flex-shrink-0", open && "rotate-180")} aria-hidden="true" />
        </Button>
        {open && (
          <div className="dropdown w-full mt-1.5 max-h-60 overflow-auto" role="listbox">
            {options.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  if (!option.disabled) {
                    onChange(option.value);
                    setOpen(false);
                  }
                }}
                disabled={option.disabled}
                className={cn(
                  "dropdown-item w-full text-left",
                  value === option.value && "bg-brand-50 text-brand-700",
                  option.disabled && "opacity-50 cursor-not-allowed"
                )}
                role="option"
                aria-selected={value === option.value}
                aria-disabled={option.disabled}
              >
                {value === option.value && <Check className="w-4 h-4 flex-shrink-0 text-brand-500" aria-hidden="true" />}
                <span className="flex-1">{option.label}</span>
              </button>
            ))}
          </div>
        )}
        {error && <span className="input-error" role="alert">{error}</span>}
        {hint && !error && <span className="input-hint">{hint}</span>}
      </div>
    </div>
  );
}

export { Dropdown, Select };