import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Play, Plus, ShieldAlert } from 'lucide-react'
import api, { formatINR, formatPct } from '../services/api'
import { PriorityBadge, StatusBadge } from '../components/Badges'
import { Loading, ErrorState } from '../components/StateViews'

const SCORE_LABELS = {
  value: 'Transaction Value',
  failure_frequency: 'Failure Frequency',
  customer_value: 'Customer Value (LTV)',
  historical_success: 'Historical Recovery Success',
  probability: 'AI Recovery Probability',
  recency: 'Recency of Failure',
}

function ScoreBar({ label, points }) {
  const pct = Math.min(100, Math.max(0, points))
  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="w-44 shrink-0 text-slate-500 dark:text-slate-400">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-full rounded-full ${pct >= 20 ? 'bg-emerald-500' : pct >= 10 ? 'bg-brand-500' : 'bg-slate-400'}`}
          style={{ width: `${pct * 4}%` }}
        />
      </div>
      <span className="w-10 text-right font-semibold tabular-nums">{points.toFixed(1)}</span>
    </div>
  )
}

const ACTION_TYPES = ['UPDATE_PAYMENT_METHOD', 'DELAYED_RETRY', 'SMART_RETRY', 'MANUAL_RISK_REVIEW', 'ABANDONED_CART_EMAIL', 'LOYALTY_OFFER']

export default function OpportunityDetail() {
  const { id } = useParams()
  const [opp, setOpp] = useState(null)
  const [error, setError] = useState(null)
  const [busyAction, setBusyAction] = useState(null)
  const [newAction, setNewAction] = useState({ action_type: 'UPDATE_PAYMENT_METHOD', channel: 'RETRY' })
  const [flash, setFlash] = useState(null)

  const load = () =>
    api.get(`/recovery/opportunities/${id}`)
      .then((r) => setOpp(r.data))
      .catch((e) => setError(e))

  useEffect(() => {
    let alive = true
    setError(null)
    load().catch((e) => alive && setError(e))
    return () => { alive = false }
  }, [id])

  if (error) return <ErrorState error={error} />
  if (!opp) return <Loading label="Loading opportunity…" />

  const approveOrExecute = async (action, verb) => {
    setBusyAction(action.id + verb)
    try {
      await api.post(`/recovery/actions/${action.id}/${verb}`, {})
      await load()
      setFlash(`Action #${action.id} ${verb === 'approve' ? 'approved' : 'executed'} successfully.`)
    } catch (e) {
      setFlash(e.response?.data?.error?.message || `Failed to ${verb} action`)
    } finally {
      setBusyAction(null)
    }
  }

  const createAction = async (e) => {
    e.preventDefault()
    try {
      await api.post(`/recovery/opportunities/${id}/actions`, newAction)
      setNewAction({ ...newAction })
      await load()
      setFlash('Recovery action queued.')
    } catch (err) {
      setFlash(err.response?.data?.error?.message || 'Could not create action')
    }
  }

  const breakdown = opp.explanation?.score_breakdown ?? {}
  const decision = opp.decisions?.[0]

  return (
    <div className="space-y-5">
      <Link to="/opportunities" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-brand-600 dark:text-slate-400">
        <ArrowLeft size={15} /> Back to pipeline
      </Link>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold tracking-tight">{opp.customer.name}</h1>
        <PriorityBadge priority={opp.priority} />
        <StatusBadge status={opp.status} />
        <span className="text-sm text-slate-400">{opp.transaction.transaction_id}</span>
        <span className="ml-auto flex items-center gap-3">
          <span className="rounded-lg bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-600 dark:bg-red-500/10 dark:text-red-400">
            {formatINR(opp.revenue_at_risk)} at risk
          </span>
          <span className="rounded-lg bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
            {formatINR(opp.expected_recovery_value)} recoverable
          </span>
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold">Customer</h2>
          <dl className="space-y-1.5 text-sm">
            {[['Customer ID', opp.customer.external_customer_id], ['Email', opp.customer.email], ['Segment', opp.customer.segment],
              ['Lifetime value', formatINR(opp.customer.lifetime_value)], ['Successful txns', opp.customer.successful_transactions],
              ['Failed txns', opp.customer.failed_transactions]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4"><dt className="text-slate-500 dark:text-slate-400">{k}</dt><dd className="truncate font-medium text-right">{v ?? '—'}</dd></div>
            ))}
          </dl>
        </div>

        <div className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold">Transaction</h2>
          <dl className="space-y-1.5 text-sm">
            {[['Amount', formatINR(opp.transaction.amount)], ['Method', opp.transaction.payment_method],
              ['Provider', opp.transaction.payment_provider], ['Status', opp.transaction.status],
              ['Attempts', opp.transaction.attempt_count], ['Created', new Date(opp.transaction.created_at).toLocaleString()]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4"><dt className="text-slate-500 dark:text-slate-400">{k}</dt><dd className="font-medium">{v}</dd></div>
            ))}
          </dl>
        </div>

        <div className="card space-y-3 p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><ShieldAlert size={15} /> Diagnosis & Model</h2>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Root cause</p><p className="font-medium">{(opp.root_cause || '').replace(/_/g, ' ')}</p></div>
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Sub cause</p><p className="font-medium truncate" title={opp.sub_cause}>{opp.sub_cause ?? '—'}</p></div>
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Recovery probability</p><p className="font-bold text-brand-600 dark:text-brand-400">{formatPct(opp.recovery_probability)}</p></div>
            <div><p className="text-xs text-slate-500 dark:text-slate-400">Score</p><p className="font-bold tabular-nums">{Math.round(opp.recovery_score)} / 100</p></div>
          </div>
          {decision && (
            <p className="rounded-lg bg-slate-50 p-2.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              Model <b>{decision.model_version}</b> · confidence {formatPct(decision.confidence, 0)}
            </p>
          )}
        </div>
      </div>

      {Object.keys(breakdown).length > 0 && (
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold">Why this score? ({Math.round(opp.recovery_score)}/100)</h2>
          <div className="space-y-2.5">
            {Object.entries(breakdown).map(([key, val]) => (
              <ScoreBar key={key} label={SCORE_LABELS[key] ?? key} points={Number(val) || 0} />
            ))}
          </div>
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{opp.explanation?.summary}</p>
        </div>
      )}

      {flash && (
        <div className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-2.5 text-sm text-brand-700 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-300">
          {flash}
        </div>
      )}

      <div className="card overflow-hidden">
        <h2 className="px-4 pt-4 text-sm font-semibold">Recovery Actions</h2>
        <table className="mt-2 min-w-full">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-800">
              {['ID', 'Type', 'Channel', 'Status', 'Approved By', '', ''].map((h) => <th key={h} className="table-head text-left">{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {opp.actions.map((a) => (
              <tr key={a.id}>
                <td className="table-cell">#{a.id}</td>
                <td className="table-cell font-medium">{a.action_type.replace(/_/g, ' ')}</td>
                <td className="table-cell">{a.channel ?? '—'}</td>
                <td className="table-cell"><StatusBadge status={a.status} /></td>
                <td className="table-cell text-xs">{a.approved_by ?? '—'}</td>
                <td className="table-cell">
                  {!['EXECUTED_SIMULATED', 'EXECUTED'].includes(a.status) && a.status === 'PENDING_APPROVAL' && (
                    <button className="btn-secondary !py-1 !px-2.5 !text-xs" disabled={busyAction === a.id + 'approve'} onClick={() => approveOrExecute(a, 'approve')}>
                      Approve
                    </button>
                  )}
                </td>
                <td className="table-cell">
                  {!['EXECUTED_SIMULATED', 'EXECUTED'].includes(a.status) && a.status !== 'PENDING_APPROVAL' && (
                    <button className="btn-primary !py-1 !px-2.5 !text-xs" disabled={busyAction === a.id + 'execute'} onClick={() => approveOrExecute(a, 'execute')}>
                      Execute
                    </button>
                  )}
                  {['EXECUTED_SIMULATED', 'EXECUTED'].includes(a.status) && (
                    <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 size={13} /> Done{a.result?.simulated ? ' (simulated)' : ''}
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {!opp.actions.length && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-slate-400">No actions yet — queue one below.</td></tr>
            )}
          </tbody>
        </table>
        <form onSubmit={createAction} className="flex flex-wrap items-end gap-2 border-t border-slate-200 p-4 dark:border-slate-800">
          <div>
            <label className="mb-1 block text-xs text-slate-500 dark:text-slate-400">Action type</label>
            <select className="input !w-auto" value={newAction.action_type} onChange={(e) => setNewAction({ ...newAction, action_type: e.target.value })}>
              {ACTION_TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500 dark:text-slate-400">Channel</label>
            <select className="input !w-auto" value={newAction.channel} onChange={(e) => setNewAction({ ...newAction, channel: e.target.value })}>
              {['EMAIL', 'SMS', 'WHATSAPP', 'RETRY', 'MANUAL_REVIEW'].map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <button type="submit" className="btn-primary"><Plus size={14} /> Queue action</button>
        </form>
      </div>

      <div className="card space-y-2 p-4">
        <h2 className="text-sm font-semibold">Recommended Strategy</h2>
        <p className="text-sm text-slate-600 dark:text-slate-300">{opp.recommended_action}</p>
        {opp.retry_policy && Object.keys(opp.retry_policy).length > 0 && (
          <pre className="overflow-x-auto rounded-lg bg-slate-950 p-3 text-xs leading-relaxed text-emerald-300">
            {JSON.stringify(opp.retry_policy, null, 2)}
          </pre>
        )}
        <div className="flex items-center gap-2 pt-1 text-xs text-slate-400">
          <Play size={12} /> Executed retries are simulated against the retry engine's success model.
        </div>
      </div>
    </div>
  )
}
