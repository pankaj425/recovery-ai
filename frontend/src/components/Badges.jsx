import clsx from 'clsx'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'

const PRIORITY_STYLES = {
  CRITICAL: 'bg-red-100 text-red-700 ring-red-600/20 dark:bg-red-500/15 dark:text-red-400',
  HIGH: 'bg-amber-100 text-amber-700 ring-amber-600/20 dark:bg-amber-500/15 dark:text-amber-400',
  MEDIUM: 'bg-blue-100 text-blue-700 ring-blue-600/20 dark:bg-blue-500/15 dark:text-blue-400',
  LOW: 'bg-slate-100 text-slate-600 ring-slate-500/20 dark:bg-slate-500/15 dark:text-slate-400',
}

const STATUS_STYLES = {
  OPEN: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
  IN_PROGRESS: 'bg-brand-100 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300',
  RECOVERED: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
  LOST: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400',
  DISMISSED: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400',
  SUCCESS: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
  FAILED: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400',
  ABANDONED: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
  PENDING: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400',
  REFUNDED: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-400',
  EXECUTED_SIMULATED: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
}

export function PriorityBadge({ priority }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset',
        PRIORITY_STYLES[priority] ?? PRIORITY_STYLES.LOW
      )}
    >
      {priority}
    </span>
  )
}

export function StatusBadge({ status }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        STATUS_STYLES[status] ?? 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400'
      )}
    >
      {(status || '').replace('_', ' ')}
    </span>
  )
}

export function KpiCard({ label, value, sublabel, delta, deltaLabel, invertDelta = false, icon: Icon }) {
  const positive = invertDelta ? (delta ?? 0) <= 0 : (delta ?? 0) >= 0
  return (
    <div className="card p-4 transition hover:shadow-md">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
        {Icon && <Icon size={16} className="text-slate-400" />}
      </div>
      <p className="mt-2 text-2xl font-bold tracking-tight">{value}</p>
      <div className="mt-1 flex items-center gap-1.5 text-xs">
        {delta != null && isFinite(delta) && (
          <span className={clsx('inline-flex items-center gap-0.5 font-semibold', positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400')}>
            {delta >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
            {Math.abs(delta).toFixed(1)}%
          </span>
        )}
        <span className="text-slate-500 dark:text-slate-400">{sublabel || deltaLabel || 'vs previous period'}</span>
      </div>
    </div>
  )
}
