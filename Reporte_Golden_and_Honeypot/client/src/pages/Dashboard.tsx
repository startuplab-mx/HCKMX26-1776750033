import { useEffect, useState } from 'react';
import axios from 'axios';
import { Database, FileText, Activity, Layers } from 'lucide-react';
import StatCard from '../components/StatCard';
import TrendsChart from '../components/TrendsChart';

interface CollectionStat { name: string; count: number }
interface Stats { totalItems: number; collections: CollectionStat[] }
interface RecentDoc {
  _id: string;
  _collection: string;
  username?: string;
  name?: string;
  text?: string;
  descripcion?: string;
  etiquetado_en?: string;
  ultima_actualizacion?: string;
  [key: string]: unknown;
}

const STAT_COLORS = ['blue', 'green', 'violet', 'orange'] as const;
const BAR_COLORS  = ['bg-blue-500', 'bg-emerald-500', 'bg-violet-500', 'bg-amber-500', 'bg-pink-500'];
const fmt = (n: string) =>
  n.replace(/_ORC$/i, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function Dashboard() {
  const [stats,   setStats]   = useState<Stats | null>(null);
  const [recent,  setRecent]  = useState<RecentDoc[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 30_000);
    return () => clearInterval(id);
  }, []);

  const fetchAll = async () => {
    try {
      const [sRes, rRes] = await Promise.all([
        axios.get('/api/stats'),
        axios.get('/api/recent?limit=15'),
      ]);
      setStats(sRes.data);
      setRecent(rRes.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const total       = stats?.totalItems || 0;
  const collections = stats?.collections || [];
  const pct         = (v: number) => (total > 0 ? (v / total) * 100 : 0);
  const topCols     = collections.slice(0, 3);

  const labelDoc = (d: RecentDoc) =>
    d.username || d.name || (d.text as string)?.slice(0, 50) ||
    (d.descripcion as string)?.slice(0, 50) || '—';

  const dateDoc = (d: RecentDoc) => {
    const raw = d.etiquetado_en || d.ultima_actualizacion;
    if (!raw) return '—';
    try {
      return new Date(String(raw)).toLocaleDateString('es-ES', {
        day: '2-digit', month: 'short', year: 'numeric',
      });
    } catch { return String(raw).slice(0, 10); }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-800">Panel de Monitoreo</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Base <span className="text-emerald-600 font-semibold">golden</span>
          {' · '}
          {new Date().toLocaleDateString('es-ES', {
            weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
          })}
        </p>
      </div>

      {/* KPI Cards */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-5 animate-pulse h-24 bg-slate-100" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Total registros" value={total}    icon={Database} color="blue"   />
          {topCols.map((c, i) => (
            <StatCard key={c.name} title={fmt(c.name)} value={c.count}
                      icon={FileText} color={STAT_COLORS[i + 1] ?? 'violet'} />
          ))}
          {topCols.length < 3 && (
            <StatCard title="Colecciones" value={collections.length} icon={Layers} color="orange" />
          )}
        </div>
      )}

      {/* Chart + Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <TrendsChart />
        </div>

        <div className="card p-5 flex flex-col gap-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Resumen</p>

          <div className="space-y-3">
            <SummaryRow label="Total registros"   value={total.toLocaleString()}           color="text-blue-600"   />
            <SummaryRow label="Colecciones"        value={String(collections.length)}       color="text-emerald-600" />
            <SummaryRow label="Mayor colección"
                        value={fmt(collections[0]?.name || '—')}
                        color="text-violet-600" />
          </div>

          <div className="border-t border-slate-100 pt-4 grid grid-cols-2 gap-3">
            <MiniBox label="Total"        value={total.toLocaleString()}           color="text-blue-600"   bg="bg-blue-50"   />
            <MiniBox label="Colecciones"  value={String(collections.length)}       color="text-emerald-600" bg="bg-emerald-50" />
          </div>
        </div>
      </div>

      {/* Distribution */}
      <div className="card p-6">
        <div className="flex items-center gap-2 mb-5">
          <Activity size={15} className="text-slate-400" />
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Distribución por colección
          </p>
        </div>
        {collections.length === 0 ? (
          <p className="text-slate-400 text-sm">Sin colecciones disponibles.</p>
        ) : (
          <div className="space-y-4">
            {collections.map((c, i) => {
              const p = pct(c.count);
              return (
                <div key={c.name}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-slate-700 font-medium">{fmt(c.name)}</span>
                    <span className="text-slate-500">
                      {c.count.toLocaleString()}
                      <span className="text-slate-400 ml-1.5">({p.toFixed(1)}%)</span>
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${BAR_COLORS[i % BAR_COLORS.length]}`}
                      style={{ width: `${Math.max(p, c.count > 0 ? 1 : 0)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Recent docs */}
      <div className="card p-6 overflow-x-auto">
        <div className="flex items-center gap-2 mb-5">
          <FileText size={15} className="text-slate-400" />
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Documentos recientes
          </p>
        </div>
        {recent.length === 0 ? (
          <p className="text-slate-400 text-sm">Sin documentos.</p>
        ) : (
          <table className="w-full min-w-[500px] text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                {['Colección', 'Identificador', 'Fecha'].map((h, i) => (
                  <th key={h}
                      className={`py-2 pb-3 text-xs font-semibold text-slate-400 uppercase tracking-wider pr-4 ${i === 2 ? 'text-right pr-0' : 'text-left'}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recent.map((doc, i) => (
                <tr key={i} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                  <td className="py-2.5 pr-4">
                    <span className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full">
                      {fmt(doc._collection)}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-slate-700">{labelDoc(doc)}</td>
                  <td className="py-2.5 text-right text-slate-400 text-xs">{dateDoc(doc)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Footer */}
      <p className="text-center text-slate-400 text-xs pb-2">
        Actualizado a las{' '}
        {new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
      </p>
    </div>
  );
}

function SummaryRow({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-slate-500 text-sm">{label}</span>
      <span className={`text-sm font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function MiniBox({ label, value, color, bg }: { label: string; value: string; color: string; bg: string }) {
  return (
    <div className={`rounded-xl ${bg} border border-slate-200 px-3 py-2.5`}>
      <p className="text-slate-500 text-xs mb-1">{label}</p>
      <p className={`font-bold text-sm ${color}`}>{value}</p>
    </div>
  );
}
