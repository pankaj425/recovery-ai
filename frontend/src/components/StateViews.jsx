import { AlertTriangle, Inbox } from 'lucide-react'

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="flex flex-col items-center gap-3 text-slate-500 dark:text-slate-400">
        <span className="h-8 w-8 animate-spin rounded-full border-[3px] border-brand-500 border-t-transparent" />
        <span className="text-sm">{label}</span>
      </div>
    </div>
  )
}

export function SkeletonRows({ rows = 6, cols = 5 }) {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r} className="border-t border-slate-100 dark:border-slate-800">
          {Array.from({ length: cols }).map((__, c) => (
            <td key={c} className="px-4 py-3"><div className="skeleton h-4 w-full max-w-[120px]" /></td>
          ))}
        </tr>
      ))}
    </tbody>
  )
}

export function EmptyState({ title, hint }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <Inbox className="text-slate-300 dark:text-slate-600" size={40} />
      <p className="font-medium text-slate-700 dark:text-slate-300">{title}</p>
      {hint && <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  )
}

export function ErrorState({ error }) {
  const message =
    error?.response?.data?.error?.message || error?.message || 'Something went wrong'
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <AlertTriangle className="text-amber-500" size={36} />
      <p className="font-medium">{message}</p>
      <p className="text-sm text-slate-500 dark:text-slate-400">Please retry or adjust your filters.</p>
    </div>
  )
}
