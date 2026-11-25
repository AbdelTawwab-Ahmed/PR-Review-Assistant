import React, { useState, useEffect } from 'react';

export const SettingsPage: React.FC = () => {
  const [healthData, setHealthData] = useState<{ status: string; cache?: string } | null>(null);

  useEffect(() => {
    fetch('/api/health/ready')
      .then((res) => res.json())
      .then(setHealthData)
      .catch(() => setHealthData({ status: 'unhealthy' }));
  }, []);

  return (
    <div className="settings-page">
      <div className="page-header-block">
        <h1 className="page-main-title">System Diagnostics & Settings</h1>
        <p className="page-subtitle">
          Operational infrastructure status and integration parameters powering the PR Review Assistant.
        </p>
      </div>

      <div className="settings-grid">
        {/* Azure OpenAI Service Card */}
        <div className="settings-card">
          <div className="card-top-row">
            <span className="card-service-icon">🧠</span>
            <span className="service-status-pill online">Active</span>
          </div>
          <h3 className="card-service-title">Azure OpenAI Service</h3>
          <p className="card-service-desc">
            Multi-agent reasoning and AST code review engines running on Microsoft Azure OpenAI.
          </p>
          <div className="config-list">
            <div className="config-item">
              <span className="config-key">Strong Deployment:</span>
              <code className="config-val">gpt-4.1</code>
            </div>
            <div className="config-item">
              <span className="config-key">Fast Deployment:</span>
              <code className="config-val">gpt-4.1-mini</code>
            </div>
            <div className="config-item">
              <span className="config-key">API Version:</span>
              <code className="config-val">2025-04-14</code>
            </div>
          </div>
        </div>

        {/* Azure Database & Cache */}
        <div className="settings-card">
          <div className="card-top-row">
            <span className="card-service-icon">⚡</span>
            <span className={`service-status-pill ${healthData?.cache === 'up' ? 'online' : 'checking'}`}>
              {healthData?.cache === 'up' ? 'Connected' : 'Verifying'}
            </span>
          </div>
          <h3 className="card-service-title">Persistence & Cache Layer</h3>
          <p className="card-service-desc">
            State checkpointing and delivery deduplication backends.
          </p>
          <div className="config-list">
            <div className="config-item">
              <span className="config-key">PostgreSQL:</span>
              <code className="config-val">gbgai2pr.postgres.database.azure.com</code>
            </div>
            <div className="config-item">
              <span className="config-key">Redis Cache:</span>
              <code className="config-val">gbgai2.redis.cache.windows.net (TLS 6380)</code>
            </div>
            <div className="config-item">
              <span className="config-key">Checkpointer:</span>
              <code className="config-val">PostgresSaver (LangGraph v2.0)</code>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
