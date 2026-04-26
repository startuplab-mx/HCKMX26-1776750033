import { BarChart3 } from 'lucide-react';

interface NavigationProps {
  currentPage: string;
  setCurrentPage: (page: string) => void;
}

export default function Navigation({ currentPage, setCurrentPage }: NavigationProps) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  ];

  return (
    <nav className="fixed top-0 left-0 right-0 bg-[#0f172a]/95 backdrop-blur-sm border-b border-[#2E6DA4]/40 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-r from-[#1B3A5C] to-[#1A4971] rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">C</span>
            </div>
            <span className="text-[#D5E8F0] font-bold text-xl hidden sm:inline">Centinela</span>
          </div>

          {/* Navigation Items */}
          <div className="flex gap-1">
            {navItems.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setCurrentPage(id)}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition-colors ${
                  currentPage === id
                    ? 'bg-[#1A4971] text-[#D5E8F0]'
                    : 'text-slate-300 hover:bg-[#1B3A5C]/45'
                }`}
              >
                <Icon size={18} />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>

          {/* User Info */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-r from-[#1B3A5C] to-[#4FC3A1] rounded-full flex items-center justify-center text-white font-bold text-xs">
              A
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
