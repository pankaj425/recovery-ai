import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { formatINR, formatPct } from '../services/api'
import { PriorityBadge, StatusBadge } from '../components/Badges'
import DataTable, { Pagination } from '../components/DataTable'
import { Loading, ErrorState, SkeletonRows } from '../components/StateViews'

const PRIORITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
const STATUSES = ['OPEN', 'IN_PROGRESS', 'RECOVERED', 'LOST', 'DISMISSED']
const CAUSES = ['PAYMENT_METHOD_ISSUE', 'BANK_OR_NETWORK', 'FRAUD_OR_RISK', 'CUSTOMER_BEHAVIOR', 'SYSTEM']

export default function Opportunities() {
  const [items, setItems] = useState(null)
  const [meta, setMeta] = useState({ total_items: 0, total_pages: 1 })
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({ priority: '', status: '', root_cause: '', search: '' })
  const [sort, setSort] = useState('expected_recovery_value')
  const [page, setPage] = useState(1)

  useEffect(() => {
    const t = setTimeout(() => {
      let alive = true
      setError(null)
      api
        .get('/recovery/opportunities', {
          params: {
            priority: filters.priority || undefined,
            status: filters.status || undefined,
            root_cause: filters.root_cause || undefined,
            search: filters.search || undefined,
            sort,
            order: 'desc',
            page,
            size: 20,
          },
        })
        .then((resp) => alive && (setItems(resp.data.items), setMeta(resp.data.meta)))
        .catch((e) => alive && setError(e))
      return () => {
        alive = false
      }
    }, filters.search ? 350 : 0)
    return () => clearTimeout(t)
  }, [filters, sort, page])

  if (error) return <ErrorState error={error} />
  if (!items && !error) return <Loading label="Loading recovery pipeline…" />

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Revenue Recovery Pipeline</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Failed payments ranked by expected recovery value — every score is explainable.
        </p>
      </div>

      <div className="card grid grid-cols-2 gap-3 p-4 lg:grid-cols-5">
        <input
          className="input col-span-2 lg:col-span-1"
          placeholder="Search customer / txn…"
          value={filters.search}
          onChange={(e) => { setPage(1); setFilters({ ...filters, search: e.target.value }) }}
        />
        <select className="input" value={filters.priority} onChange={(e) => { setPage(1); setFilters({ ...filters, priority: e.target.value }) }}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="input" value={filters.status} onChange={(e) => { setPage(1); setFilters({ ...filters, status: e.target.value }) }}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
        </select>
        <select className="input" value={filters.root_cause} onChange={(e) => { setPage(1); setFilters({ ...filters, root_cause: e.target.value }) }}>
          <option value="">All root causes</option>
          {CAUSES.map((c) => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
        </select>
        <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="expected_recovery_value">Sort: Expected ₹</option>
          <option value="recovery_score">Sort: Score</option>
          <option value="revenue_at_risk">Sort: Amount</option>
          <option value="created_at">Sort: Newest</option>
        </select>
      </div>

      <DataTable
        columns={[
          { key: 'priority', label: 'Priority' },
          { key: 'customer', label: 'Customer' },
          { key: 'amount', label: 'Amount', align: 'right' },
          { key: 'cause', label: 'Root Cause' },
          { key: 'prob', label: 'Probability', align: 'right' },
          { key: 'expected', label: 'Expected ₹', align: 'right' },
          { key: 'score', label: 'Score', align: 'right' },
          { key: 'status', label: 'Status' },
          { key: 'action', label: 'Recommended Action' },
        ]}
      >
        {!items ? (
          <SkeletonRows cols={9} />
        ) : (
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {items.map((o) => (
              <tr key={o.id} className="transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="table-cell"><PriorityBadge priority={o.priority} /></td>
                <td className="table-cell">
                  <Link to={`/opportunities/${o.id}`} className="font-medium hover:text-brand-600 dark:hover:text-brand-400">
                    {o.customer.name}
                  </Link>
                  <span className="block text-xs text-slate-400">{o.transaction.transaction_id}</span>
                </td>
                <td className="table-cell text-right font-medium">{formatINR(o.revenue_at_risk)}</td>
                <td className="table-cell">
                  <span className="text-xs">{(o.root_cause || '').replace(/_/g, ' ')}</span>
                </td>
                <td className="table-cell text-right">{formatPct(o.recovery_probability, 0)}</td>
                <td className="table-cell text-right font-semibold text-emerald-600 dark:text-emerald-400">
                  {formatINR(o.expected_recovery_value)}
                </td>
                <td className="table-cell text-right tabular-nums">{Math.round(o.recovery_score)}</td>
                <td className="table-cell"><StatusBadge status={o.status} /></td>
                <td className="table-cell max-w-[180px] truncate text-xs" title={o.recommended_action}>{o.recommended_action}</td>
              </tr>
            ))}
            {!items.length && (
              <tr><td colSpan={9} className="px-4 py-12 text-center text-sm text-slate-400">No opportunities match these filters.</td></tr>
            )}
          </tbody>
        )}
      </DataTable>

      <Pagination page={page} totalPages={meta.total_pages} totalItems={meta.total_items} onPage={setPage} />
    </div>
  )
}
