import { useEffect, useRef, useState } from 'react'
import { Bot, Lightbulb, Send, Sparkles, TrendingUp, Wrench } from 'lucide-react'
import api, { formatINR } from '../services/api'
import { Loading } from '../components/StateViews'

const SUGGESTIONS = [
  'How much revenue can we potentially recover?',
  'What are my top 3 recovery opportunities right now?',
  'Show me all failed transactions for cus_rahul01',
  'What are the most common failure reasons this week?',
  'Which payment method loses us the most money?',
]

function AssistantMessage({ msg }) {
  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white">
        <Bot size={16} />
      </div>
      <div className="min-w-0 flex-1 space-y-2.5 rounded-xl rounded-tl-sm border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.answer}</p>

        {msg.metrics?.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {msg.metrics.map((m, i) => (
              <div key={i} className="rounded-lg bg-brand-50 px-3 py-1.5 text-xs dark:bg-brand-500/10">
                <span className="text-slate-500 dark:text-slate-400">{m.label}: </span>
                <b className={m.value > 0 ? 'text-emerald-600 dark:text-emerald-400' : ''}>
                  {typeof m.value === 'number' && m.label.toLowerCase().includes('₹') ? formatINR(m.value) : m.value.toLocaleString?.() ?? m.value}
                </b>
              </div>
            ))}
          </div>
        )}

        {msg.insights?.length > 0 && (
          <div>
            <p className="mb-1 flex items-center gap-1 text-xs font-semibold text-slate-500 dark:text-slate-400"><Lightbulb size={12} /> Insights</p>
            <ul className="list-disc space-y-1 pl-5 text-xs text-slate-600 dark:text-slate-300">
              {msg.insights.map((ins, i) => <li key={i}>{ins}</li>)}
            </ul>
          </div>
        )}

        {msg.recommendations?.length > 0 && (
          <div>
            <p className="mb-1 flex items-center gap-1 text-xs font-semibold text-slate-500 dark:text-slate-400"><TrendingUp size={12} /> Recommendations</p>
            <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-200">
              {msg.recommendations.map((rec, i) => <li key={i}>{typeof rec === 'string' ? rec : rec.text ?? rec.action}</li>)}
            </ol>
          </div>
        )}

        {msg.tools_used?.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <Wrench size={11} className="text-slate-400" />
            {msg.tools_used.map((t) => (
              <span key={t} className="rounded-full border border-dashed border-slate-300 px-2 py-0.5 font-mono text-[10px] text-slate-400 dark:border-slate-600">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Assistant() {
  const [messages, setMessages] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    let alive = true
    // Seed the conversation with an opening summary so the page is never empty.
    api.post('/ai/chat', { message: 'Give me a quick recovery status summary' })
      .then((r) => alive && setMessages([{ role: 'assistant', ...r.data }]))
      .catch(() => alive && setMessages([{ role: 'assistant', answer: 'Hi! Ask me anything about your failed payments and recovery opportunities.' }]))
    return () => { alive = false }
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  const send = async (text) => {
    const message = (text ?? input).trim()
    if (!message || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', answer: message }])
    setBusy(true)
    try {
      const resp = await api.post('/ai/chat', { message })
      setMessages((m) => [...m, { role: 'assistant', ...resp.data }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', answer: e.response?.data?.error?.message || 'Sorry — I hit an error. Please try again.' }])
    } finally {
      setBusy(false)
    }
  }

  if (!messages) return <Loading label="Waking up your assistant…" />

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-4xl flex-col">
      <div className="mb-3 flex items-center gap-2">
        <h1 className="text-xl font-bold tracking-tight">AI Recovery Assistant</h1>
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400">
          <Sparkles size={10} /> tool-calling agent
        </span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {messages.map((msg, i) =>
          msg.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-md rounded-xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-sm text-white shadow-sm">
                {msg.answer}
              </div>
            </div>
          ) : (
            <AssistantMessage key={i} msg={msg} />
          )
        )}
        {busy && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white"><Bot size={16} /></div>
            <div className="rounded-xl rounded-tl-sm border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <span className="flex gap-1">
                {[0, 150, 300].map((d) => (
                  <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-500" style={{ animationDelay: `${d}ms` }} />
                ))}
              </span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => send(s)} disabled={busy}
            className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 transition hover:border-brand-400 hover:text-brand-600 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300">
            {s}
          </button>
        ))}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send() }} className="mt-2 flex gap-2 pb-1">
        <input
          className="input"
          placeholder="Ask about opportunities, customers, failure reasons, revenue…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button type="submit" className="btn-primary" disabled={busy || !input.trim()}>
          <Send size={15} /> Send
        </button>
      </form>
    </div>
  )
}
