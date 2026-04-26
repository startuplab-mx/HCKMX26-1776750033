import { useState } from 'react';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import './App.css';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f172a] via-[#12243a] to-[#1a2e47]">
      <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} />
      <main className="pt-16">
        {currentPage === 'dashboard' && <Dashboard />}
      </main>
    </div>
  );
}

export default App;
