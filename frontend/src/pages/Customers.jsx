import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { formatINR, formatPct } from '../services/api'
import DataTable, { Pagination } from '../components/DataTable'
import { Loading, ErrorState, SkeletonRows, EmptyState } from '../components/StateViews'
import { SegmentChart } from '../components/charts/Charts'

const SEGMENTS = ['HIGH', 'MEDIUM', 'LOW']

function CustomerDrawer({ customerId, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setData(null)
    setError(null)
    api.get(`/customers/${customerId}`)
      .then((r) => alive && setData(r.data.data))
      .catch((e) => alive && setError(e))
    return () => { alive = false }
  }, [customerId])

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <aside className="h-full w-full max-w-md overflow-y-auto bg-white p-5 shadow-xl dark:bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold">{data ? data.customer.name : 'Loading…'}</h2>
          <button className="btn-secondary !px-2.5 !py-1 !text-xs" onClick={onClose}>Close</button>
        </div>

        {error && <ErrorState error={error} />}
        {!data && !error && <Loading label="Analyzing customer…" />}

        {data && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-3 gap-2">
              {[['LTV', formatINR(data.metrics.lifetime_value)], ['Success', `${formatPct(data.metrics.success_rate, 0)}`], ['Failures', String(data.metrics.failed_transactions)]].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-slate-50 p-2.5 text-center dark:bg-slate-800">
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">{k}</p>
                  <p className="font-bold">{v}</p>
                </div>
              ))}
            </div>

            <dl className="space-y-1.5">
              {[['Customer ID', data.customer.external_customer_id], ['Email', data.customer.email],
                ['Segment', data.customer.segment], ['Successful txns', String(data.metrics.successful_transactions)],
                ['Avg txn value', formatINR(data.metrics.average_transaction_value)]].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4"><dt className="text-slate-500 dark:text-slate-400">{k}</dt><dd className="truncate font-medium">{v}</dd></div>
              ))}
            </dl>

            {data.insights?.length > 0 && (
              <div>
                <h3 className="mb-1.5 font-semibold">AI Insights</h3>
                <ul className="list-disc space-y-1 pl-4 text-slate-600 dark:text-slate-300">
                  {data.insights.map((insight, i) => <li key={i}>{insight}</li>)}
                </ul>
              </div>
            )}

            {data.recent_failures?.length > 0 && (
              <div>
                <h3 className="mb-1.5 font-semibold">Recent Failures</h3>
                <ul className="space-y-1.5">
                  {data.recent_failures.map((f) => (
                    <li key={f.transaction_id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-xs dark:border-slate-700">
                      <span className="font-mono">{f.transaction_id}</span>
                      <span>{f.failure_code?.replace(/_/g, ' ').toLowerCase()}</span>
                      <span className="font-medium">{formatINR(f.amount)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <Link to={`/opportunities?search=${encodeURIComponent(data.customer.external_customer_id)}`} className="btn-secondary w-full">
              View recovery opportunities
            </Link>
          </div>
        )}
      </aside>
    </div>
  )
}

export default function Customers() {
  const [items, setItems] = useState(null)
  const [meta, setMeta] = useState({ total_items: 0 })
  const [segmentsData, setSegmentsData] = useState([])
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({ search: '', segment: '' })
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    let alive = true
    setError(null)
    api.get('/analytics/segments').then((r) => alive && setSegmentsData(r.data.data)).catch(() => {})
    api
      .get('/customers', {
        params: { search: filters.search || undefined, segment: filters.segment || undefined, page, size: 25 },
      })
      .then((resp) => alive && (setItems(resp.data.items), setMeta(resp.data.meta)))
      .catch((e) => alive && setError(e))
    return () => { alive = false }
  }, [filters, page])

  if (error) return <ErrorState error={error} />
  if (!items) return <Loading label="Loading customers…" />

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Customers</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">{meta.total_items.toLocaleString('en-IN')} customers · click a row for AI analysis</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        <div className="card p-4 xl:col-span-1">
          <h2 className="mb-2 text-sm font-semibold">Value Segments</h2>
          <SegmentChart data={segmentsData} />
        </div>

        <div className="space-y-3 xl:col-span-3">
          <div className="card grid grid-cols-2 gap-3 p-4">
            <input
              className="input"
              placeholder="Search name / email / ID…"
              value={filters.search}
              onChange={(e) => { setPage(1); setFilters({ ...filters, search: e.target.value }) }}
            />
            <select className="input" value={filters.segment} onChange={(e) => { setPage(1); setFilters({ ...filters, segment: e.target.value }) }}>
              <option value="">All segments</option>
              {SEGMENTS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>

          <DataTable
            columns={[
              { key: 'name', label: 'Customer' },
              { key: 'segment', label: 'Segment' },
              { key: 'ltv', label: 'Lifetime Value', align: 'right' },
              { key: 'success', label: 'Successful', align: 'right' },
              { key: 'failed', label: 'Failed', align: 'right' },
            ]}
          >
            {!items.length ? (
              <tbody><tr><td colSpan={5}><EmptyState title="No customers match" hint="Try a different search term or segment." /></td></tr></tbody>
            ) : (
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {items.map((c) => (
                  <tr key={c.external_customer_id} onClick={() => setSelected(c.external_customer_id)} className="cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <td className="table-cell">
                      <span className="font-medium">{c.name}</span>
                      <span className="block text-xs text-slate-400">{c.email}</span>
                    </td>
                    <td className="table-cell">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        c.segment === 'HIGH' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400'
                        : c.segment === 'MEDIUM' ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400'}`}>
                        {c.segment}
                      </span>
                    </td>
                    <td className="table-cell text-right font-medium">{formatINR(c.lifetime_value)}</td>
                    <td className="table-cell text-right tabular-nums">{c.successful_transactions}</td>
                    <td className={`table-cell text-right tabular-nums ${c.failed_transactions > 0 ? 'font-semibold text-red-500' : ''}`}>
                      {c.failed_transactions}
                    </td>
                  </tr>
                ))}
              </tbody>
            )}
          </DataTable>

          <Pagination page={page} totalPages={Math.max(1, Math.ceil(meta.total_items / 25))} totalItems={meta.total_items} onPage={setPage} />
        </div>
      </div>

      {selected && <CustomerDrawer customerId={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
