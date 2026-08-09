"use client";

import { cn } from "@/lib/utils";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
  align?: "left" | "right" | "center";
  className?: string;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  rowKey: (row: T) => string;
  pageSize?: number;
  emptyMessage?: string;
  className?: string;
}

/** Sortable/paginated table shell. Callers own responsiveness — on narrow
 * screens, wrap this in `hidden md:block` and render a card list alongside
 * it for mobile (see `TeamCapacityGrid` for the pattern), since a dense
 * table is not a good mobile layout regardless of scroll handling. */
export function DataTable<T>({
  columns,
  data,
  rowKey,
  pageSize = 20,
  emptyMessage = "Kayıt bulunamadı",
  className,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return data;
    const copy = [...data];
    copy.sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [data, sortKey, sortDir, columns]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const paged = sorted.slice(safePage * pageSize, safePage * pageSize + pageSize);

  const toggleSort = (col: DataTableColumn<T>) => {
    if (!col.sortValue) return;
    if (sortKey === col.key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col.key);
      setSortDir("asc");
    }
    setPage(0);
  };

  return (
    <div className={cn("overflow-x-auto rounded-xl border border-border bg-surface", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-surface-2 border-b border-border">
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => toggleSort(col)}
                className={cn(
                  "px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-text-muted whitespace-nowrap",
                  col.align === "right" && "text-right",
                  col.align === "center" && "text-center",
                  col.sortValue && "cursor-pointer select-none hover:text-text"
                )}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortValue &&
                    (sortKey === col.key ? (
                      sortDir === "asc" ? (
                        <ArrowUp className="w-3 h-3" />
                      ) : (
                        <ArrowDown className="w-3 h-3" />
                      )
                    ) : (
                      <ChevronsUpDown className="w-3 h-3 opacity-40" />
                    ))}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {paged.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-text-muted">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            paged.map((row) => (
              <tr
                key={rowKey(row)}
                className="border-b border-border last:border-0 hover:bg-hover transition-colors"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      "px-4 py-3 align-middle",
                      col.align === "right" && "text-right",
                      col.align === "center" && "text-center",
                      col.className
                    )}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-text-muted">
          <span>
            {safePage * pageSize + 1}–{Math.min(sorted.length, (safePage + 1) * pageSize)} / {sorted.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              disabled={safePage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="px-2 py-1 rounded-lg border border-border disabled:opacity-40 hover:bg-hover transition-colors"
            >
              Önceki
            </button>
            <button
              disabled={safePage >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              className="px-2 py-1 rounded-lg border border-border disabled:opacity-40 hover:bg-hover transition-colors"
            >
              Sonraki
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
