import { useEffect, useState } from 'react'
import api, { formatINR, formatPct } from '../services/api'
import { Loading, ErrorState } from '../components/StateViews'
import { MethodPerformanceChart } from '../components/charts/Charts'

export default function PaymentMethods() {
  const [methods, setMethods] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    api.get('/analytics/payment-methods')
      .then((r) => alive && setMethods(r.data.data))
      .catch((e) => alive && setError(e))
    return () => { alive = false }
  }, [])

  if (error) return <ErrorState error={error} />
  if (!methods) return <Loading label="Analyzing payment methods…" />

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Payment Method Performance</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Where money flows — and where it gets stuck. Estimated recoverable comes from open AI-scored opportunities.
        </p>
      </div>

      <div className="card p-4">
        <h2 className="mb-3 text-sm font-semibold">Successful Volume vs Revenue Lost</h2>
        <MethodPerformanceChart data={methods} />
      </div>

      <div className="card overflow-hidden">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-800/60">
            <tr>
              {['Method', 'Transactions', 'Success Rate', 'Failure Rate', 'Successful Volume', 'Revenue Lost', 'Estimated Recoverable'].map((h, i) => (
                <th key={h} className={`table-head ${i > 0 ? 'text-right' : ''}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {methods.map((m) => (
              <tr key={m.method} className="transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="table-cell font-semibold">{m.method}</td>
                <td className="table-cell text-right tabular-nums">{m.transactions.toLocaleString('en-IN')}</td>
                <td className="table-cell text-right tabular-nums text-emerald-600 dark:text-emerald-400">{formatPct(m.success_rate)}</td>
                <td className={`table-cell text-right tabular-nums ${m.failure_rate > 0.2 ? 'font-semibold text-red-500' : ''}`}>{formatPct(m.failure_rate)}</td>
                <td className="table-cell text-right font-medium">{formatINR(m.successful_volume, true)}</td>
                <td className="table-cell text-right font-medium text-red-500">{formatINR(m.revenue_lost, true)}</td>
                <td className="table-cell text-right font-semibold text-emerald-600 dark:text-emerald-400">{formatINR(m.estimated_recoverable, true)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card p-4">
        <h2 className="mb-2 text-sm font-semibold">Failure Codes by Value at Risk</h2>
        <FailureCodeTable />
      </div>
    </div>
  )
}

function FailureCodeTable() {
  const [rows, setRows] = useState([])
  useEffect(() => {
    let alive = true
    api.get('/analytics/failure-reasons').then((r) => alive && setRows(r.data.data.slice(0, 10))).catch(() => {})
    return () => { alive = false }
  }, [])
  if (!rows.length) return <p className="py-6 text-center text-sm text-slate-400">No failure data.</p>
  return (
    <div className="space-y-2.5">
      {rows.map((r) => {
        const max = rows[0].value_at_risk || 1
        return (
          <div key={r.code} className="flex items-center gap-3 text-xs">
            <span className="w-48 shrink-0 font-medium capitalize">{r.code.replace(/_/g, ' ').toLowerCase()}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-400" style={{ width: `${(r.value_at_risk / max) * 100}%` }} />
            </div>
            <span className="w-20 text-right tabular-nums text-slate-500 dark:text-slate-400">{r.count} txns</span>
            <span className="w-24 text-right font-semibold tabular-nums">{formatINR(r.value_at_risk, true)}</span>
          </div>
        )
      })}
    </div>
  )
}
