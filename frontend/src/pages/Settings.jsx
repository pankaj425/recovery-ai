import { useEffect, useState } from 'react'
import { KeyRound, Server, Webhook as WebhookIcon } from 'lucide-react'
import api from '../services/api'
import { useAuth } from '../context/AuthContext'

function Row({ k, v, mono = false }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-2 text-sm last:border-0 dark:border-slate-800">
      <span className="text-slate-500 dark:text-slate-400">{k}</span>
      <span className={mono ? 'font-mono text-xs' : 'font-medium'}>{v}</span>
    </div>
  )
}

export default function Settings() {
  const { user } = useAuth()
  const [health, setHealth] = useState(null)
  const [webhookSecretVisible, setWebhookSecretVisible] = useState(false)

  useEffect(() => {
    let alive = true
    api.get('/auth/me').then((r) => alive && setHealth((h) => ({ ...h, me: r.data }))).catch(() => {})
    return () => { alive = false }
  }, [])

  const secret = import.meta.env.VITE_WEBHOOK_SECRET || '(set WEBHOOK_SECRET on the backend — dev mode accepts unsigned webhooks)'

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Account and integration configuration.</p>
      </div>

      <section className="card p-5">
        <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold"><KeyRound size={15} /> Account</h2>
        <Row k="Name" v={user?.name ?? '—'} />
        <Row k="Email" v={user?.email ?? '—'} />
        <Row k="Role" v={(user?.role ?? 'MERCHANT').toUpperCase()} />
        <Row k="Auth method" v="JWT bearer token (30-minute expiry)" />
      </section>

      <section className="card p-5">
        <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Server size={15} /> Backend API</h2>
        <Row k="Base URL" v="/api/v1 (proxied to FastAPI on :8000)" mono />
        <Row k="Docs" v={<a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="text-brand-600 hover:underline dark:text-brand-400">Swagger UI</a>} />
        <Row k="Rate limit" v="120 requests / minute / IP" />
      </section>

      <section className="card p-5">
        <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold"><WebhookIcon size={15} /> Webhook Ingestion</h2>
        <Row
          k="Endpoint"
          v={
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs dark:bg-slate-800">
              POST /api/v1/webhook/payment-failed
            </code>
          }
        />
        <Row k="Signature header" v="X-Signature (HMAC-SHA256 of raw body)" mono />
        <Row k="Signing secret" v={
          <button onClick={() => setWebhookSecretVisible((s) => !s)} className="text-brand-600 hover:underline dark:text-brand-400">
            {webhookSecretVisible ? secret : '•••••••••••• reveal'}
          </button>
        } />
        <Row k="Idempotency" v="event_id unique — duplicates are ignored" />
        <Row k="Async mode" v="?sync=false queues processing in the background worker" />
      </section>

      <section className="card border-red-200 p-5 dark:border-red-500/30">
        <h2 className="text-sm font-semibold text-red-600 dark:text-red-400">Demo environment</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          This deployment runs on a synthetic dataset with simulated recovery actions — no real emails, SMS,
          or payment gateway calls are ever made.
        </p>
      </section>
    </div>
  )
}
