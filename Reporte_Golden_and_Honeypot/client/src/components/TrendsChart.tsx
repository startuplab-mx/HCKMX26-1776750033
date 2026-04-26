import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import axios from 'axios';
import { TrendingUp } from 'lucide-react';

interface TrendPoint {
  _id: { source: string; date: string };
  count: number;
}

const PALETTE = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4'];

const fmt = (n: string) =>
  n.replace(/_ORC$/i, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const tooltipStyle = {
  backgroundColor: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: '0.5rem',
  color: '#0f172a',
  fontSize: '0.8rem',
  boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
};

export default function TrendsChart() {
  const [data,    setData]    = useState<Record<string, string | number>[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [chartType, setChartType] = useState<'bar' | 'line'>('bar');

  useEffect(() => { fetchTrends(); }, []);

  const fetchTrends = async () => {
    try {
      const res = await axios.get<TrendPoint[]>('/api/trends');
      const trends = res.data;
      const uniqueSources = [...new Set(trends.map((t) => t._id.source))];
      setSources(uniqueSources);

      const grouped: Record<string, Record<string, string | number>> = {};
      trends.forEach((t) => {
        const { date, source } = t._id;
        if (!grouped[date]) grouped[date] = { date };
        grouped[date][source] = t.count;
      });

      setData(
        Object.values(grouped).sort((a, b) => String(a.date).localeCompare(String(b.date)))
      );
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card p-6 flex items-center justify-center h-72">
        <p className="text-slate-400 text-sm animate-pulse">Cargando tendencias…</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="card p-6 flex items-center justify-center h-72">
        <p className="text-slate-400 text-sm">Sin datos en los últimos 30 días.</p>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex justify-between items-center mb-5">
        <div className="flex items-center gap-2">
          <TrendingUp size={17} className="text-blue-500" />
          <h2 className="text-sm font-semibold text-slate-700">Tendencias — últimos 30 días</h2>
        </div>
        <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
          {(['bar', 'line'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setChartType(t)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                chartType === t
                  ? 'bg-white text-slate-800 shadow-sm border border-slate-200'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {t === 'bar' ? 'Barras' : 'Línea'}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        {chartType === 'bar' ? (
          <BarChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
            <Legend formatter={(v) => <span style={{ color: '#64748b', fontSize: 11 }}>{fmt(v)}</span>} />
            {sources.map((src, i) => (
              <Bar key={src} dataKey={src} name={src} fill={PALETTE[i % PALETTE.length]}
                   radius={[3, 3, 0, 0]} maxBarSize={36} fillOpacity={0.9} />
            ))}
          </BarChart>
        ) : (
          <LineChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: '#e2e8f0' }} />
            <Legend formatter={(v) => <span style={{ color: '#64748b', fontSize: 11 }}>{fmt(v)}</span>} />
            {sources.map((src, i) => (
              <Line key={src} type="monotone" dataKey={src} name={src}
                    stroke={PALETTE[i % PALETTE.length]} strokeWidth={2.5}
                    dot={{ r: 3, fill: PALETTE[i % PALETTE.length] }} activeDot={{ r: 5 }} />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
