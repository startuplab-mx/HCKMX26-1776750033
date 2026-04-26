import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: LucideIcon;
  color: 'blue' | 'green' | 'violet' | 'orange';
  trend?: { value: number; positive: boolean };
}

const styles: Record<string, { icon: string; value: string; pill: string }> = {
  blue:   { icon: 'bg-blue-100 text-blue-600',    value: 'text-blue-700',   pill: 'bg-blue-50 border-blue-100' },
  green:  { icon: 'bg-emerald-100 text-emerald-600', value: 'text-emerald-700', pill: 'bg-emerald-50 border-emerald-100' },
  violet: { icon: 'bg-violet-100 text-violet-600', value: 'text-violet-700', pill: 'bg-violet-50 border-violet-100' },
  orange: { icon: 'bg-amber-100 text-amber-600',  value: 'text-amber-700',  pill: 'bg-amber-50 border-amber-100' },
};

export default function StatCard({ title, value, icon: Icon, color, trend }: StatCardProps) {
  const s = styles[color];
  return (
    <div className={`card stat-card p-5 border ${s.pill}`}>
      <div className="flex justify-between items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider mb-2">{title}</p>
          <p className={`text-3xl font-bold leading-none ${s.value}`}>
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {trend && (
            <p className={`text-xs mt-2 font-medium ${trend.positive ? 'text-emerald-600' : 'text-red-500'}`}>
              {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </p>
          )}
        </div>
        <div className={`p-2.5 rounded-xl ${s.icon} flex-shrink-0`}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  );
}
