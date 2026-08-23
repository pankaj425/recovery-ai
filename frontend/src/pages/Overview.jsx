import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, IndianRupee, ShieldAlert, TrendingDown, Wallet } from 'lucide-react'
import api, { formatINR, formatPct } from '../services/api'
import { KpiCard, PriorityBadge, StatusBadge } from '../components/Badges'
import { Loading, ErrorState } from '../components/StateViews'
import {
  FailureDonut, MethodPerformanceChart, RevenueTrendChart, StatusAreaChart,
} from '../components/charts/Charts'

export default function Overview() {
  const [metrics, setMetrics] = useState(null)
  const [trends, setTrends] = useState(null)
  const [reasons, setReasons] = useState(null)
  const [methods, setMethods] = useState(null)
  const [topOpps, setTopOpps] = useState([])
  const [error, setError] = useState(null)
  const [days, setDays] = useState(30)

  useEffect(() => {
    let alive = true
    setError(null)
    Promise.all([
      api.get('/analytics/revenue', { params: { days } }),
      api.get('/analytics/trends', { params: { days } }),
      api.get('/analytics/failure-reasons'),
      api.get('/analytics/payment-methods'),
      api.get('/recovery/opportunities', { params: { size: 6, sort: 'expected_recovery_value' } }),
    ])
      .then(([rev, trn, fr, pm, opps]) => {
        if (!alive) return
        setMetrics(rev.data.data)
        setTrends(trn.data.data)
        setReasons(fr.data.data.slice(0, 5))
        setMethods(pm.data.data)
        setTopOpps(opps.data.items)
      })
      .catch((e) => alive && setError(e))
    return () => {
      alive = false
    }
  }, [days])

  if (error) return <ErrorState error={error} />
  if (!metrics) return <Loading label="Crunching your payment data…" />

  const c = metrics.comparison

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Revenue Overview</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Last {metrics.period_days} days · live database figures</p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-900">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                days === d ? 'bg-brand-600 text-white' : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {d}D
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard
          label="Revenue at Risk" value={formatINR(metrics.revenue_at_risk)} icon={ShieldAlert}
          delta={c.revenue_at_risk.delta_pct} sublabel="failed + abandoned value"
        />
        <KpiCard
          label="Potentially Recoverable" value={formatINR(metrics.potential_recoverable_revenue)} icon={Wallet}
          delta={c.potential_recoverable_revenue.delta_pct} sublabel={`${formatPct(metrics.recovery_rate)} of at-risk`}
        />
        <KpiCard
          label="Failed Payment Rate" value={formatPct(metrics.failure_rate)} icon={TrendingDown}
          delta={c.failure_rate.delta_pct} invertDelta sublabel="vs previous period"
        />
        <KpiCard
          label="Successful Revenue" value={formatINR(metrics.successful_revenue)} icon={IndianRupee}
          delta={c.successful_revenue.delta_pct} sublabel={`${metrics.total_transactions.toLocaleString('en-IN')} txns analyzed`}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="card p-4 xl:col-span-2">
          <h2 className="mb-3 text-sm font-semibold">Revenue Trend</h2>
          <RevenueTrendChart data={trends} />
        </div>
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold">Failure Reasons (value at risk)</h2>
          {reasons.length ? <FailureDonut data={reasons} /> : <p className="py-16 text-center text-sm text-slate-400">No failures in this window 🎉</p>}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="card p-4 xl:col-span-2">
          <h2 className="mb-3 text-sm font-semibold">Successful vs Failed Payments</h2>
          <StatusAreaChart data={trends} />
        </div>
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold">Payment Method Performance</h2>
          <MethodPerformanceChart data={methods} />
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-4 pt-4">
          <h2 className="text-sm font-semibold">Top Recovery Opportunities</h2>
          <Link to="/opportunities" className="text-xs font-medium text-brand-600 hover:underline dark:text-brand-400">
            View all →
          </Link>
        </div>
        <table className="mt-2 min-w-full">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-800">
              <th className="table-head">Priority</th><th className="table-head">Customer</th>
              <th className="table-head text-right">Amount</th><th className="table-head text-right">Attempts</th>
              <th className="table-head text-right">Probability</th><th className="table-head text-right">Expected Recovery</th>
              <th className="table-head">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {topOpps.map((o) => (
              <tr key={o.id} className="transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="table-cell"><PriorityBadge priority={o.priority} /></td>
                <td className="table-cell">
                  <Link to={`/opportunities/${o.id}`} className="font-medium hover:text-brand-600 dark:hover:text-brand-400">
                    {o.customer.name}
                  </Link>
                  <span className="block text-xs text-slate-400">{o.transaction.transaction_id}</span>
                </td>
                <td className="table-cell text-right font-medium">{formatINR(o.revenue_at_risk)}</td>
                <td className="table-cell text-right">{o.transaction.attempt_count}</td>
                <td className="table-cell text-right">{formatPct(o.recovery_probability, 0)}</td>
                <td className="table-cell text-right font-semibold text-emerald-600 dark:text-emerald-400">
                  {formatINR(o.expected_recovery_value)}
                </td>
                <td className="table-cell"><StatusBadge status={o.status} /></td>
              </tr>
            ))}
            {!topOpps.length && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-slate-400">No open opportunities.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
