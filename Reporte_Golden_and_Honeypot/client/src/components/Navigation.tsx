import { BarChart3, Shield } from 'lucide-react';

interface NavigationProps {
  currentPage: string;
  setCurrentPage: (page: string) => void;
}

export default function Navigation({ currentPage, setCurrentPage }: NavigationProps) {
  const navItems = [{ id: 'dashboard', label: 'Dashboard', icon: BarChart3 }];

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-14">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
              <Shield size={14} className="text-white" />
            </div>
            <span className="text-slate-800 font-bold text-base hidden sm:inline">
              Centinela <span className="text-blue-500 font-normal text-sm">golden</span>
            </span>
          </div>

          <div className="flex gap-1">
            {navItems.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setCurrentPage(id)}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-2 text-sm font-medium transition-all ${
                  currentPage === id
                    ? 'bg-blue-50 text-blue-700 border border-blue-200'
                    : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
                }`}
              >
                <Icon size={15} />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>

          <div className="w-7 h-7 bg-emerald-100 border border-emerald-200 rounded-full flex items-center justify-center text-emerald-700 font-bold text-xs">
            G
          </div>
        </div>
      </div>
    </nav>
  );
}
