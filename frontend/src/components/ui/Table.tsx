"use client";

import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Column<T> {
  key: string;
  header: string;
  accessor: keyof T | ((row: T) => ReactNode);
  className?: string;
  width?: string;
  align?: "left" | "center" | "right";
  render?: (value: unknown, row: T) => ReactNode;
}

export interface TableProps<T> extends HTMLAttributes<HTMLTableElement> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  emptyMessage?: string;
  loading?: boolean;
  rowClassName?: (row: T) => string;
  onRowClick?: (row: T) => void;
  striped?: boolean;
  hoverable?: boolean;
  stickyHeader?: boolean;
}

export function Table<T>({
  className,
  columns,
  data,
  keyExtractor,
  emptyMessage = "No data available",
  loading = false,
  rowClassName,
  onRowClick,
  striped = true,
  hoverable = true,
  stickyHeader = false,
  ...props
}: TableProps<T>) {
  const isEmpty = data.length === 0 && !loading;

  return (
    <div className={cn("table-container", className)} {...props}>
      {loading ? (
        <div className="p-8 text-center">
          <div className="animate-pulse space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-12 bg-surface-200 rounded animate-pulse" />
            ))}
          </div>
        </div>
      ) : isEmpty ? (
        <div className="p-8 text-center text-surface-500">
          {emptyMessage}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className={cn("table", stickyHeader && "sticky-header")} {...props}>
            <thead className={cn(stickyHeader && "sticky top-0 z-10 bg-surface-50")}>
              <tr>
                {columns.map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    className={cn(
                      "px-4 py-3 text-left font-medium text-surface-600 bg-surface-50 border-b border-surface-200",
                      column.className,
                      stickyHeader && "sticky top-0 z-10 bg-surface-50"
                    )}
                    style={{ width: column.width, textAlign: column.align }}
                  >
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, index) => (
                <tr
                  key={keyExtractor(row)}
                  className={cn(
                    striped && index % 2 === 1 && "bg-surface-50",
                    hoverable && "hover:bg-surface-50 transition-colors",
                    onRowClick && "cursor-pointer",
                    rowClassName?.(row)
                  )}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        "px-4 py-3 border-b border-surface-100 text-surface-700",
                        column.className
                      )}
                      style={{ width: column.width, textAlign: column.align }}
                    >
                      {column.render
                        ? column.render(column.accessor instanceof Function ? column.accessor(row) : row[column.accessor as keyof T], row)
                        : column.accessor instanceof Function
                        ? column.accessor(row)
                        : String(row[column.accessor as keyof T] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

Table.displayName = "Table";

export { Table };