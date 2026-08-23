import { useEffect, useState } from 'react'
import { ArrowRight, Bot, RefreshCcw } from 'lucide-react'
import api, { formatINR, formatPct } from '../services/api'
import { Loading, ErrorState } from '../components/StateViews'
import { PriorityDistributionChart } from '../components/charts/Charts'

function CompareBar({ label, baseline, ai, suffix }) {
  const max = Math.max(baseline, ai) || 1
  const width = (v) => `${Math.max(3, (v / max) * 100)}%`
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <div className="flex items-center gap-2">
        <span className="w-16 text-right text-xs text-slate-400">Baseline</span>
        <div className="h-5 flex-1 overflow-hidden rounded-md bg-slate-100 dark:bg-slate-800">
          <div className="flex h-full items-center justify-end rounded-md bg-slate-400 pr-2 text-[10px] font-semibold text-white" style={{ width: width(baseline) }}>
            {suffix === '₹' ? formatINR(baseline, true) : `${baseline}${suffix}`}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-16 text-right text-xs text-slate-400">RecoveryAI</span>
        <div className="h-5 flex-1 overflow-hidden rounded-md bg-slate-100 dark:bg-slate-800">
          <div className="flex h-full items-center justify-end rounded-md bg-gradient-to-r from-brand-500 to-emerald-500 pr-2 text-[10px] font-bold text-white" style={{ width: width(ai) }}>
            {suffix === '₹' ? formatINR(ai, true) : `${ai}${suffix}`}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Analytics() {
  const [summary, setSummary] = useState(null)
  const [cohort, setCohort] = useState(null)
  const [priorities, setPriorities] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setError(null)
    Promise.all([
      api.get('/analytics/recovered-revenue'),
      api.get('/analytics/baseline-comparison', { params: { sample_size: 100 } }),
      api.get('/analytics/priorities'),
    ])
      .then(([s, c, p]) => {
        if (!alive) return
        setSummary(s.data.data)
        setCohort(c.data.data)
        setPriorities(p.data.data)
      })
      .catch((e) => alive && setError(e))
    return () => { alive = false }
  }, [])

  if (error) return <ErrorState error={error} />
  if (!summary || !cohort) return <Loading label="Comparing baseline vs AI-assisted recovery…" />

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Analytics — Baseline vs RecoveryAI</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          The counterfactual every judge asks for: what rule-based dunning recovers vs. what the AI engine recovers.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-4 p-5">
          <h2 className="text-sm font-semibold">Whole Book (all failed & abandoned revenue)</h2>
          <CompareBar label="Recovery rate" baseline={summary.baseline_recovery_rate_pct} ai={summary.ai_recovery_rate_pct} suffix="%" />
          <CompareBar label="Recovered revenue" baseline={summary.baseline_recovered_revenue} ai={summary.ai_assisted_recovered_revenue} suffix="₹" />
          <div className="grid grid-cols-2 gap-3 border-t border-slate-200 pt-3 text-sm dark:border-slate-800">
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Revenue at risk</p><p className="font-bold">{formatINR(summary.revenue_at_risk)}</p></div>
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Incremental with AI</p><p className="font-bold text-emerald-600 dark:text-emerald-400">{formatINR(summary.incremental_recovered_revenue)}</p></div>
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Improvement multiple</p><p className="font-bold">{summary.improvement_multiple?.toFixed(2)}×</p></div>
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Low-value retries avoided</p><p className="font-bold">{(summary.unnecessary_retries_avoided ?? 0).toLocaleString('en-IN')}</p></div>
          </div>
        </div>

        <div className="card space-y-4 p-5">
          <h2 className="text-sm font-semibold">Top-{cohort.cohort_size} Opportunity Cohort</h2>
          <CompareBar label="Recovery rate" baseline={cohort.baseline_recovery_rate * 100} ai={cohort.ai_assisted_recovery_rate * 100} suffix="%" />
          <CompareBar label="Recovered revenue" baseline={cohort.baseline_recovered} ai={cohort.ai_assisted_recovered} suffix="₹" />
          <div className="grid grid-cols-2 gap-3 border-t border-slate-200 pt-3 text-sm dark:border-slate-800">
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Cohort at-risk value</p><p className="font-bold">{formatINR(cohort.total_at_risk)}</p></div>
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Incremental recovered</p><p className="font-bold text-emerald-600 dark:text-emerald-400">{formatINR(cohort.incremental)}</p></div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold">Open Opportunities by Priority</h2>
          <PriorityDistributionChart data={priorities.map(({ priority, count }) => ({ priority, count }))} />
        </div>

        <div className="card space-y-3 p-5">
          <h2 className="text-sm font-semibold">Priority Queue Snapshot</h2>
          {priorities.map((p) => (
            <div key={p.priority} className="flex items-center justify-between border-b border-slate-100 pb-2 last:border-0 dark:border-slate-800">
              <span className={`w-20 rounded-full px-2 py-0.5 text-center text-xs font-bold ${
                p.priority === 'CRITICAL' ? 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400'
                : p.priority === 'HIGH' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400'
                : p.priority === 'MEDIUM' ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400'
                : 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400'}`}>
                {p.priority}
              </span>
              <span className="text-sm tabular-nums">{p.count.toLocaleString('en-IN')} opportunities</span>
              <span className="text-sm text-slate-500 dark:text-slate-400">{formatINR(p.value_at_risk, true)} at risk</span>
              <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">{formatINR(p.expected_recovery, true)} expected</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card flex flex-wrap items-center justify-between gap-3 bg-gradient-to-r from-brand-600 to-brand-500 p-5 text-white">
        <div className="max-w-xl">
          <h2 className="font-bold">The AI difference</h2>
          <p className="mt-0.5 text-sm text-brand-50">
            Rule-based dunning retries everyone blindly. RecoveryAI predicts which payments will recover
            ({formatPct(summary.ai_assisted_recovery_rate, 0)} vs {formatPct(summary.baseline_recovery_rate, 0)} baseline),
            skips hopeless ones, and escalates high-value risks for human review.
          </p>
        </div>
        <RefreshCcw size={40} className="opacity-60" />
      </div>
    </div>
  )
}
