import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';

export const Sidebar: React.FC = () => {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('/api/health');
        setIsHealthy(res.ok);
      } catch {
        setIsHealthy(false);
      }
    };
    check();
    const interval = setInterval(check, 20000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="saas-sidebar">
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div className="brand-logo-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </div>
        <div className="brand-text">
          <span className="brand-title">PR Assistant</span>
          <span className="brand-badge">LangGraph AI</span>
        </div>
      </div>

      {/* Main Nav Section */}
      <div className="sidebar-section">
        <span className="section-label">WORKSPACE</span>
        <nav className="sidebar-nav">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="9" rx="1" />
              <rect x="14" y="3" width="7" height="5" rx="1" />
              <rect x="14" y="12" width="7" height="9" rx="1" />
              <rect x="3" y="16" width="7" height="5" rx="1" />
            </svg>
            <span>Dashboard</span>
          </NavLink>

          <NavLink
            to="/repositories"
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
            <span>Repositories</span>
          </NavLink>

          <NavLink
            to="/history"
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>Analysis History</span>
          </NavLink>

          <NavLink
            to="/settings"
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            <span>Settings</span>
          </NavLink>
        </nav>
      </div>

      {/* Sidebar Footer with Live Beacon */}
      <div className="sidebar-footer">
        <div className="health-card">
          <div className="health-header">
            <span
              className={`health-dot ${
                isHealthy === true ? 'healthy' : isHealthy === false ? 'unhealthy' : 'checking'
              }`}
            />
            <span className="health-text">
              {isHealthy === true ? 'Azure Cloud Live' : isHealthy === false ? 'API Offline' : 'Connecting...'}
            </span>
          </div>
          <span className="health-sub">Azure OpenAI GPT-4.1 Ready</span>
        </div>

        <a
          href="https://github.com/AbdelTawwab-Ahmed/PR-Review-Assistant"
          target="_blank"
          rel="noopener noreferrer"
          className="sidebar-repo-link"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
          </svg>
          <span>GitHub Repository</span>
          <span className="ext-icon">&nearr;</span>
        </a>
      </div>
    </aside>
  );
};
