import { useEffect, useState } from 'react';
import axios from 'axios';
import { Youtube, MessageCircle, Radio, TrendingUp, Activity, Database } from 'lucide-react';
import StatCard from '../components/StatCard';
import TrendsChart from '../components/TrendsChart';

interface Stats {
  totalItems: number;
  totalChannels: number;
  itemsBySource: Array<{
    _id: string;
    count: number;
    totalViews: number;
    totalLikes: number;
  }>;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000); // Actualizar cada 30 segundos
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const youtubeStats = stats?.itemsBySource?.find((s) => s._id === 'youtube');
  const telegramStats = stats?.itemsBySource?.find((s) => s._id === 'telegram');
  const tiktokStats = stats?.itemsBySource?.find((s) => s._id === 'tiktok');

  const totalItems = stats?.totalItems || 0;
  const safePercent = (value: number) => (totalItems > 0 ? (value / totalItems) * 100 : 0);

  const sourceBreakdown = [
    {
      key: 'youtube',
      label: 'YouTube',
      count: youtubeStats?.count || 0,
      views: youtubeStats?.totalViews || 0,
      likes: youtubeStats?.totalLikes || 0,
      color: 'bg-[#1B3A5C]',
    },
    {
      key: 'telegram',
      label: 'Telegram',
      count: telegramStats?.count || 0,
      views: telegramStats?.totalViews || 0,
      likes: 0,
      color: 'bg-[#2E6DA4]',
    },
    {
      key: 'tiktok',
      label: 'TikTok',
      count: tiktokStats?.count || 0,
      views: tiktokStats?.totalViews || 0,
      likes: tiktokStats?.totalLikes || 0,
      color: 'bg-[#4FC3A1]',
    },
  ];

  const totalViews = sourceBreakdown.reduce((acc, current) => acc + current.views, 0);
  const totalLikes = sourceBreakdown.reduce((acc, current) => acc + current.likes, 0);

  const sourceMetrics = sourceBreakdown.map((source) => {
    const share = safePercent(source.count);
    const avgViews = source.count > 0 ? source.views / source.count : 0;
    const engagementPer1kViews = source.views > 0 ? (source.likes / source.views) * 1000 : 0;
    return {
      ...source,
      share,
      avgViews,
      engagementPer1kViews,
    };
  });

  const topSource = [...sourceMetrics].sort((a, b) => b.count - a.count)[0];
  const activeSources = sourceMetrics.filter((source) => source.count > 0).length;
  const concentration = topSource?.share || 0;
  const avgViewsPerItem = totalItems > 0 ? totalViews / totalItems : 0;
  const likesPer1kViews = totalViews > 0 ? (totalLikes / totalViews) * 1000 : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-[#D5E8F0] mb-2">Panel de Monitoreo</h1>
        <p className="text-slate-300">
          {new Date().toLocaleDateString('es-ES', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })}
        </p>
      </div>

      {/* KPI Cards */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-6 animate-pulse">
              <div className="h-8 bg-[#1B3A5C] rounded w-3/4 mb-2"></div>
              <div className="h-10 bg-[#1B3A5C] rounded w-1/2"></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            title="Total de Contenido"
            value={stats?.totalItems || 0}
            icon={TrendingUp}
            color="blue"
          />
          <StatCard
            title="Videos YouTube"
            value={youtubeStats?.count || 0}
            icon={Youtube}
            color="navy"
          />
          <StatCard
            title="Mensajes Telegram"
            value={telegramStats?.count || 0}
            icon={MessageCircle}
            color="blue"
          />
          <StatCard
            title="Videos TikTok"
            value={tiktokStats?.count || 0}
            icon={Radio}
            color="green"
          />
        </div>
      )}

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trends Chart - Takes 2 columns */}
        <div className="lg:col-span-2">
          <TrendsChart />
        </div>

        {/* Quick Stats */}
        <div className="card p-6">
          <h2 className="text-xl font-bold text-[#D5E8F0] mb-4 flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#1A4971]"></div>
            Resumen Rápido
          </h2>

          <div className="space-y-4">
            <div>
              <p className="text-slate-300 text-sm mb-1">Engagement YouTube</p>
              <p className="text-2xl font-bold text-[#A8D5BA]">
                {youtubeStats?.totalLikes?.toLocaleString() || 0}
              </p>
            </div>
            <div className="border-t border-slate-600"></div>
            <div>
              <p className="text-slate-300 text-sm mb-1">Visualizaciones Telegram</p>
              <p className="text-2xl font-bold text-[#D5E8F0]">
                {telegramStats?.totalViews?.toLocaleString() || 0}
              </p>
            </div>
            <div className="border-t border-slate-600"></div>
            <div>
              <p className="text-slate-300 text-sm mb-1">Total Canales Telegram</p>
              <p className="text-2xl font-bold text-[#4FC3A1]">
                {stats?.totalChannels || 0}
              </p>
            </div>
            <div className="border-t border-slate-600 mt-4"></div>
            <div className="grid grid-cols-2 gap-3 text-xs text-slate-300 mt-4">
              <div className="rounded-lg border border-[#2E6DA4]/40 bg-[#12243A]/60 px-3 py-2">
                <p className="mb-1 flex items-center gap-1"><Database size={13} /> Registros</p>
                <p className="text-[#D5E8F0] font-semibold">{totalItems.toLocaleString()}</p>
              </div>
              <div className="rounded-lg border border-[#2E6DA4]/40 bg-[#12243A]/60 px-3 py-2">
                <p className="mb-1 flex items-center gap-1"><Activity size={13} /> Vistas Totales</p>
                <p className="text-[#D5E8F0] font-semibold">{totalViews.toLocaleString()}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Source Coverage */}
      <div className="card p-6">
        <h2 className="text-xl font-bold text-[#D5E8F0] mb-5">Cobertura por Fuente</h2>
        <div className="space-y-4">
          {sourceMetrics.map((source) => {
            return (
              <div key={source.key}>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-slate-200 font-medium">{source.label}</span>
                  <span className="text-slate-300">
                    {source.count.toLocaleString()} ({source.share.toFixed(1)}%)
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-[#0f1f33] overflow-hidden">
                  <div
                    className={`h-full ${source.color}`}
                    style={{ width: `${Math.max(source.share, 1)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Operational Intelligence */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="card p-5">
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Fuente dominante</p>
          <p className="text-2xl font-bold text-[#D5E8F0]">{topSource?.label || 'N/D'}</p>
          <p className="text-sm text-slate-300 mt-2">{concentration.toFixed(1)}% del volumen total</p>
        </div>
        <div className="card p-5">
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Cobertura activa</p>
          <p className="text-2xl font-bold text-[#4FC3A1]">{activeSources}/3</p>
          <p className="text-sm text-slate-300 mt-2">Fuentes con actividad en el dataset</p>
        </div>
        <div className="card p-5">
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Vistas por registro</p>
          <p className="text-2xl font-bold text-[#D5E8F0]">{Math.round(avgViewsPerItem).toLocaleString()}</p>
          <p className="text-sm text-slate-300 mt-2">Promedio global de densidad</p>
        </div>
        <div className="card p-5">
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Likes por 1k vistas</p>
          <p className="text-2xl font-bold text-[#A8D5BA]">{likesPer1kViews.toFixed(2)}</p>
          <p className="text-sm text-slate-300 mt-2">Índice agregado de interacción</p>
        </div>
      </div>

      {/* Source Performance Table */}
      <div className="card p-6 overflow-x-auto">
        <h2 className="text-xl font-bold text-[#D5E8F0] mb-4">Rendimiento por Fuente</h2>
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="text-slate-400 border-b border-slate-700">
              <th className="text-left py-2 font-medium">Fuente</th>
              <th className="text-right py-2 font-medium">Registros</th>
              <th className="text-right py-2 font-medium">% Cobertura</th>
              <th className="text-right py-2 font-medium">Views Totales</th>
              <th className="text-right py-2 font-medium">Views/Registro</th>
              <th className="text-right py-2 font-medium">Likes/1k views</th>
            </tr>
          </thead>
          <tbody>
            {sourceMetrics.map((source) => (
              <tr key={source.key} className="border-b border-slate-800/70 text-slate-200">
                <td className="py-3 font-medium">{source.label}</td>
                <td className="py-3 text-right">{source.count.toLocaleString()}</td>
                <td className="py-3 text-right">{source.share.toFixed(1)}%</td>
                <td className="py-3 text-right">{source.views.toLocaleString()}</td>
                <td className="py-3 text-right">{Math.round(source.avgViews).toLocaleString()}</td>
                <td className="py-3 text-right">{source.engagementPer1kViews.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer Info */}
      <div className="card p-4 text-center text-slate-300 text-sm">
        <p>
          Datos actualizados hace{' '}
          {new Date().toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })}
        </p>
      </div>
    </div>
  );
}
