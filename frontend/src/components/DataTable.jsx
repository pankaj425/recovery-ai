import { ChevronLeft, ChevronRight } from 'lucide-react'
import clsx from 'clsx'

export default function DataTable({ columns, children, className }) {
  return (
    <div className={clsx('card overflow-hidden', className)}>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-800/60">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={clsx('table-head whitespace-nowrap', col.align === 'right' && 'text-right', col.className)}
                >
                  {col.sortable ? (
                    <button className="inline-flex items-center gap-1 uppercase hover:text-brand-600" onClick={() => col.onSort?.(col)}>
                      {col.label}
                      {col.sorted && <span aria-hidden>{col.sortDir === 'asc' ? '▲' : '▼'}</span>}
                    </button>
                  ) : (
                    col.label
                  )}
                </th>
              ))}
            </tr>
          </thead>
          {children}
        </table>
      </div>
    </div>
  )
}

export function Pagination({ page, totalPages, totalItems, onPage }) {
  if (!totalItems) return null
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
      <span>
        Page {page} of {totalPages} · {totalItems.toLocaleString('en-IN')} records
      </span>
      <div className="flex items-center gap-1">
        <button className="btn-secondary !px-2 !py-1.5" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft size={15} />
        </button>
        <button className="btn-secondary !px-2 !py-1.5" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  )
}
