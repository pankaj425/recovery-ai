import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const AXIS = { stroke: '#94a3b8', fontSize: 11 }
const GRID = '#e2e8f0'
const TOOLTIP_STYLE = {
  backgroundColor: 'rgba(15,23,42,0.92)',
  border: 'none',
  borderRadius: 8,
  color: '#f1f5f9',
  fontSize: 12,
}

const compact = (v) => {
  const abs = Math.abs(v)
  if (abs >= 1e7) return `${(v / 1e7).toFixed(1)}Cr`
  if (abs >= 1e5) return `${(v / 1e5).toFixed(1)}L`
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`
  return v
}

const money = (v) => `₹${compact(v)}`
export const CHART_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#0ea5e9', '#a855f7']

export function RevenueTrendChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} tickFormatter={(d) => String(d).slice(5)} />
        <YAxis tick={AXIS} tickFormatter={compact} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v, name) => [money(v), name]} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="successful_value" name="Successful" stroke="#10b981" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="at_risk_value" name="At risk" stroke="#ef4444" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function StatusAreaChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} tickFormatter={(d) => String(d).slice(5)} />
        <YAxis tick={AXIS} allowDecimals={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area type="monotone" dataKey="successful_count" name="Successful" stackId="1" stroke="#10b981" fill="#10b98133" />
        <Area type="monotone" dataKey="failed_count" name="Failed/Abandoned" stackId="1" stroke="#ef4444" fill="#ef444433" />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function FailureDonut({ data }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value_at_risk"
          nameKey="code"
          innerRadius={55}
          outerRadius={90}
          paddingAngle={2}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v, n) => [money(v), n]} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function MethodPerformanceChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="method" tick={AXIS} />
        <YAxis tick={AXIS} tickFormatter={compact} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v, name) => [money(v), name]} cursor={{ fill: '#94a3b81a' }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="successful_volume" name="Successful volume" fill="#6366f1" radius={[4, 4, 0, 0]} />
        <Bar dataKey="revenue_lost" name="Revenue lost" fill="#f59e0b" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function PriorityDistributionChart({ data }) {
  const colors = { CRITICAL: '#ef4444', HIGH: '#f59e0b', MEDIUM: '#0ea5e9', LOW: '#94a3b8' }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
        <XAxis type="number" tick={AXIS} allowDecimals={false} />
        <YAxis type="category" dataKey="priority" tick={AXIS} width={72} />
        <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: '#94a3b81a' }} />
        <Bar dataKey="count" name="Opportunities" radius={[0, 4, 4, 0]}>
          {data.map((entry) => (
            <Cell key={entry.priority} fill={colors[entry.priority] ?? '#94a3b8'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function SegmentChart({ data }) {
  const colors = { HIGH: '#10b981', MEDIUM: '#0ea5e9', LOW: '#94a3b8' }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="segment" tick={AXIS} />
        <YAxis tick={AXIS} tickFormatter={compact} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`₹${new Intl.NumberFormat('en-IN').format(Math.round(v))}`, 'Total LTV']} cursor={{ fill: '#94a3b81a' }} />
        <Bar dataKey="lifetime_value" name="Lifetime value" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.segment} fill={colors[entry.segment] ?? '#6366f1'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
