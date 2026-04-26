import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: LucideIcon;
  color: 'blue' | 'green' | 'navy' | 'orange';
  trend?: {
    value: number;
    positive: boolean;
  };
}

const colorMap = {
  blue: 'from-[#2E6DA4] to-[#D5E8F0]',
  green: 'from-[#1E8449] to-[#4FC3A1]',
  navy: 'from-[#1B3A5C] to-[#1A4971]',
  orange: 'from-[#E67E22] to-[#C0392B]',
};

export default function StatCard({ title, value, icon: Icon, color, trend }: StatCardProps) {
  return (
    <div className="card stat-card p-6">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-slate-300 text-sm font-medium mb-2">{title}</p>
          <p className="stat-value">{value.toLocaleString()}</p>
          {trend && (
            <p className={`text-xs mt-2 ${trend.positive ? 'text-[#4FC3A1]' : 'text-[#C0392B]'}`}>
              {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}% este mes
            </p>
          )}
        </div>
        <div className={`p-3 rounded-lg bg-gradient-to-br ${colorMap[color]}`}>
          <Icon size={24} className="text-white" />
        </div>
      </div>
    </div>
  );
}
