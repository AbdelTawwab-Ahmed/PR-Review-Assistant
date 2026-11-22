import React, { useState, useEffect } from 'react';

export const SettingsPage: React.FC = () => {
  const [healthData, setHealthData] = useState<{ status: string; cache?: string } | null>(null);
  const [copiedWebhook, setCopiedWebhook] = useState(false);
  const [copiedSecret, setCopiedSecret] = useState(false);

  const webhookUrl = 'https://gpgai2-ghdvf7b6caetf3ds.westus3-01.azurewebsites.net/api/webhooks/github';
  const webhookSecret = '••••••••••••••••••••••••••••••••';

  useEffect(() => {
    fetch('/api/health/ready')
      .then((res) => res.json())
      .then(setHealthData)
      .catch(() => setHealthData({ status: 'unhealthy' }));
  }, []);

  const copyToClipboard = (text: string, setCopied: (v: boolean) => void) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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

        {/* GitHub Webhook Configuration Card */}
        <div className="settings-card full-width">
          <div className="card-top-row">
            <span className="card-service-icon">🪝</span>
            <span className="service-status-pill online">Ready</span>
          </div>
          <h3 className="card-service-title">GitHub Webhook Integration</h3>
          <p className="card-service-desc">
            Configure this webhook in any GitHub repository settings to receive automated instant reviews on pull request events.
          </p>

          <div className="webhook-field-group">
            <label className="field-label">Payload URL</label>
            <div className="copy-input-row">
              <input type="text" readOnly value={webhookUrl} className="readonly-input" />
              <button
                type="button"
                onClick={() => copyToClipboard(webhookUrl, setCopiedWebhook)}
                className="btn btn-secondary btn-sm"
              >
                {copiedWebhook ? 'Copied! ✓' : 'Copy'}
              </button>
            </div>
          </div>

          <div className="webhook-field-group">
            <label className="field-label">Webhook Secret (HMAC SHA-256)</label>
            <div className="copy-input-row">
              <input type="text" readOnly value={webhookSecret} className="readonly-input" />
              <button
                type="button"
                onClick={() => copyToClipboard(webhookSecret, setCopiedSecret)}
                className="btn btn-secondary btn-sm"
              >
                {copiedSecret ? 'Copied! ✓' : 'Copy'}
              </button>
            </div>
          </div>

          <div className="webhook-instructions">
            <strong>Required Events:</strong> Select <code>Let me select individual events</code> &rarr; check <code>Pull requests</code>. Secret is configured securely in Azure backend.
          </div>
        </div>
      </div>
    </div>
  );
};
