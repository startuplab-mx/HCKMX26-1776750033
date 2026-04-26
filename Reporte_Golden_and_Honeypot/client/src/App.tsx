import { useState } from 'react';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import './App.css';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');

  return (
    <div className="min-h-screen bg-[#f5f7fa]">
      <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} />
      <main className="pt-14">
        {currentPage === 'dashboard' && <Dashboard />}
      </main>
    </div>
  );
}

export default App;
