import { Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardPage } from './pages/DashboardPage';
import { RepositoriesPage } from './pages/RepositoriesPage';
import { HistoryPage } from './pages/HistoryPage';
import { SettingsPage } from './pages/SettingsPage';
import { RunDetailPage } from './pages/RunDetailPage';

export default function App() {
  return (
    <div className="saas-app-layout">
      <Sidebar />
      <div className="saas-main-viewport">
        <Header />
        <main className="saas-main-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/repositories" element={<RepositoriesPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/runs/:runId" element={<RunDetailPage />} />
            <Route path="/runs/*" element={<RunDetailPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
