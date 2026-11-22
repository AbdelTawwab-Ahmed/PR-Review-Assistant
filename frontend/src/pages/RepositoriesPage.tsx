import React, { useState, useEffect } from 'react';
import {
  getListeningRepos,
  startListeningRepo,
  stopListeningRepo,
} from '../api/repos';

export const RepositoriesPage: React.FC = () => {
  const [monitoredRepos, setMonitoredRepos] = useState<string[]>([]);
  const [inputUrl, setInputUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    getListeningRepos().then((r) => setMonitoredRepos(r.repositories)).catch(() => {});
  }, []);

  const handleAddListening = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputUrl.trim()) return;

    try {
      setIsLoading(true);
      const res = await startListeningRepo(inputUrl.trim());
      setMsg({ type: 'success', text: res.message });
      setInputUrl('');
      const updated = await getListeningRepos();
      setMonitoredRepos(updated.repositories);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to start listening to repo.';
      setMsg({ type: 'error', text: message });
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopListening = async (repo: string) => {
    try {
      await stopListeningRepo(repo);
      setMonitoredRepos((prev) => prev.filter((r) => r !== repo));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="repositories-page">
      <div className="page-header-block">
        <h1 className="page-main-title">Repository Monitoring & Watcher</h1>
        <p className="page-subtitle">
          Add any GitHub repository to watch for pull requests. The AI assistant automatically evaluates PRs as soon as they are opened.
        </p>
      </div>

      {/* Add Continuous Listener Card */}
      <div className="connect-repo-card">
        <div className="connect-header">
          <span className="pulse-green-dot" />
          <h3 className="connect-title">Live Repository Watcher</h3>
        </div>
        <p className="connect-desc">
          Add any repository URL to continuously watch. Our background worker periodically scans for newly opened or updated pull requests and initiates automated reviews.
        </p>

        <form onSubmit={handleAddListening} className="connect-form">
          <input
            type="text"
            placeholder="https://github.com/owner/repo or owner/repo"
            value={inputUrl}
            onChange={(e) => setInputUrl(e.target.value)}
            className="connect-input"
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !inputUrl.trim()} className="btn btn-primary">
            {isLoading ? 'Connecting...' : '🎧 Start Listening'}
          </button>
        </form>

        {msg && (
          <div className={`connect-msg ${msg.type}`}>
            <span>{msg.text}</span>
          </div>
        )}

        {/* Monitored Repos Chips */}
        {monitoredRepos.length > 0 && (
          <div className="active-listening-box">
            <span className="active-label">Actively Monitored Repositories ({monitoredRepos.length}):</span>
            <div className="active-chips">
              {monitoredRepos.map((r) => (
                <div key={r} className="active-repo-chip">
                  <span className="pulse-green-dot small" />
                  <span className="active-repo-name">{r}</span>
                  <button onClick={() => handleStopListening(r)} className="chip-remove" title="Remove">
                    &times;
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
