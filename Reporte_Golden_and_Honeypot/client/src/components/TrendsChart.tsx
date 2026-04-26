import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import axios from 'axios';
import { Activity } from 'lucide-react';

interface Trend {
  _id: {
    source: string;
    date: string;
  };
  count: number;
  totalViews: number;
  totalEngagement: number;
}

interface ChartData {
  date: string;
  YouTube: number;
  Telegram: number;
  TikTok: number;
}

export default function TrendsChart() {
  const [data, setData] = useState<ChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [chartType, setChartType] = useState<'line' | 'bar'>('line');

  useEffect(() => {
    fetchTrends();
  }, []);

  const fetchTrends = async () => {
    try {
      const response = await axios.get('/api/trends');
      const trends: Trend[] = response.data;

      // Agrupar por fecha
      const groupedData: { [key: string]: any } = {};

      trends.forEach((trend) => {
        const date = trend._id.date;
        const source = trend._id.source === 'youtube' ? 'YouTube' :
                       trend._id.source === 'telegram' ? 'Telegram' : 'TikTok';

        if (!groupedData[date]) {
          groupedData[date] = { date };
        }
        groupedData[date][source] = trend.count;
      });

      const chartData = Object.values(groupedData).sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
      );

      setData(chartData);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching trends:', error);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card p-6">
        <p className="text-slate-300">Cargando tendencias...</p>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <Activity className="text-[#1A4971]" size={24} />
          <h2 className="text-xl font-bold text-[#D5E8F0]">Tendencias (últimos 30 días)</h2>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setChartType('line')}
            className={`px-3 py-1 rounded text-sm ${
              chartType === 'line'
                ? 'bg-[#1A4971] text-[#D5E8F0]'
                : 'bg-[#1B3A5C]/40 text-slate-300'
            }`}
          >
            Línea
          </button>
          <button
            onClick={() => setChartType('bar')}
            className={`px-3 py-1 rounded text-sm ${
              chartType === 'bar'
                ? 'bg-[#1A4971] text-[#D5E8F0]'
                : 'bg-[#1B3A5C]/40 text-slate-300'
            }`}
          >
            Barras
          </button>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        {chartType === 'line' ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2E6DA4" />
            <XAxis dataKey="date" stroke="#D5E8F0" />
            <YAxis stroke="#D5E8F0" />
            <Tooltip
              contentStyle={{
                backgroundColor: '#12243A',
                border: '1px solid #2E6DA4',
                borderRadius: '0.5rem',
                color: '#D5E8F0',
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="YouTube"
              stroke="#1B3A5C"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="Telegram"
              stroke="#2E6DA4"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="TikTok"
              stroke="#4FC3A1"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2E6DA4" />
            <XAxis dataKey="date" stroke="#D5E8F0" />
            <YAxis stroke="#D5E8F0" />
            <Tooltip
              contentStyle={{
                backgroundColor: '#12243A',
                border: '1px solid #2E6DA4',
                borderRadius: '0.5rem',
                color: '#D5E8F0',
              }}
            />
            <Legend />
            <Bar dataKey="YouTube" fill="#1B3A5C" />
            <Bar dataKey="Telegram" fill="#2E6DA4" />
            <Bar dataKey="TikTok" fill="#4FC3A1" />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
