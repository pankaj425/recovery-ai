import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { formatINR, formatPct } from '../services/api'
import { StatusBadge } from '../components/Badges'
import DataTable, { Pagination } from '../components/DataTable'
import { Loading, ErrorState, SkeletonRows } from '../components/StateViews'

const STATUSES = ['SUCCESS', 'FAILED', 'ABANDONED', 'PENDING']
const METHODS = ['CARD', 'UPI', 'NETBANKING', 'WALLET']

export default function Transactions() {
  const [items, setItems] = useState(null)
  const [meta, setMeta] = useState({ total_items: 0, total_pages: 1 })
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({ status: '', payment_method: '', search: '' })
  const [page, setPage] = useState(1)

  useEffect(() => {
    let alive = true
    setError(null)
    api
      .get('/transactions', {
        params: {
          status: filters.status || undefined,
          payment_method: filters.payment_method || undefined,
          search: filters.search || undefined,
          page,
          size: 25,
        },
      })
      .then((resp) => alive && (setItems(resp.data.items), setMeta(resp.data.meta)))
      .catch((e) => alive && setError(e))
    return () => { alive = false }
  }, [filters, page])

  if (error) return <ErrorState error={error} />
  if (!items) return <Loading label="Loading transactions…" />

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Transactions</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">{meta.total_items.toLocaleString('en-IN')} transactions in the ledger</p>
      </div>

      <div className="card grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
        <input
          className="input col-span-2"
          placeholder="Search txn id / customer…"
          value={filters.search}
          onChange={(e) => { setPage(1); setFilters({ ...filters, search: e.target.value }) }}
        />
        <select className="input" value={filters.status} onChange={(e) => { setPage(1); setFilters({ ...filters, status: e.target.value }) }}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select className="input" value={filters.payment_method} onChange={(e) => { setPage(1); setFilters({ ...filters, payment_method: e.target.value }) }}>
          <option value="">All methods</option>
          {METHODS.map((m) => <option key={m}>{m}</option>)}
        </select>
      </div>

      <DataTable
        columns={[
          { key: 'txn', label: 'Transaction' },
          { key: 'amount', label: 'Amount', align: 'right' },
          { key: 'method', label: 'Method / Provider' },
          { key: 'status', label: 'Status' },
          { key: 'failure', label: 'Failure Reason' },
          { key: 'attempts', label: 'Attempts', align: 'right' },
          { key: 'date', label: 'Date', align: 'right' },
        ]}
      >
        {!items.length ? (
          <tbody><tr><td colSpan={7} className="px-4 py-12 text-center text-sm text-slate-400">No transactions found.</td></tr></tbody>
        ) : (
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {items.map((t) => (
              <tr key={t.transaction_id} className="transition hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="table-cell">
                  <span className="font-mono text-xs font-medium">{t.transaction_id}</span>
                </td>
                <td className="table-cell text-right font-medium">{formatINR(t.amount)}</td>
                <td className="table-cell text-xs">
                  {t.payment_method}
                  <span className="block text-slate-400">{t.payment_provider}</span>
                </td>
                <td className="table-cell"><StatusBadge status={t.status} /></td>
                <td className="table-cell max-w-[220px] text-xs">
                  {t.failure_code ? (
                    <>
                      <span className="font-medium">{t.failure_code.replace(/_/g, ' ').toLowerCase()}</span>
                      <span className="block truncate text-slate-400" title={t.failure_reason}>{t.failure_reason}</span>
                    </>
                  ) : '—'}
                </td>
                <td className="table-cell text-right tabular-nums">{t.attempt_count}</td>
                <td className="table-cell whitespace-nowrap text-right text-xs text-slate-500 dark:text-slate-400">
                  {new Date(t.created_at).toLocaleDateString()}{' '}
                  {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTable>

      <Pagination page={page} totalPages={meta.total_pages} totalItems={meta.total_items} onPage={setPage} />
    </div>
  )
}
