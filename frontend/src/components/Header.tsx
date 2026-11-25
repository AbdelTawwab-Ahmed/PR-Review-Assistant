import React from 'react';
import { useLocation } from 'react-router-dom';

export const Header: React.FC = () => {
  const location = useLocation();

  const getPageTitle = () => {
    if (location.pathname === '/') return 'AI Code Review Dashboard';
    if (location.pathname.startsWith('/repositories')) return 'Connected Repositories';
    if (location.pathname.startsWith('/history')) return 'Analysis History';
    if (location.pathname.startsWith('/settings')) return 'System Diagnostics & Settings';
    if (location.pathname.startsWith('/runs/')) return 'PR Analysis & Review Inspection';
    return 'Dashboard';
  };

  return (
    <header className="saas-header">
      <div className="header-left">
        <h2 className="header-title">{getPageTitle()}</h2>
      </div>

      <div className="header-right">
        <div className="status-pill-badge">
          <span className="pulse-indicator" />
          <span>Azure Multi-Agent Swarm</span>
        </div>
      </div>
    </header>
  );
};
