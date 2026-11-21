import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getUserRepos,
  getListeningRepos,
  startListeningRepo,
  stopListeningRepo,
  type UserRepoItem,
} from '../api/repos';

export const RepositoriesPage: React.FC = () => {
  const navigate = useNavigate();
  const [userRepos, setUserRepos] = useState<UserRepoItem[]>([]);
  const [monitoredRepos, setMonitoredRepos] = useState<string[]>([]);
  const [inputUrl, setInputUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    getUserRepos().then(setUserRepos).catch(() => {});
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
    } catch (err: any) {
      setMsg({ type: 'error', text: err?.message || 'Failed to start listening to repo.' });
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
        <h1 className="page-main-title">Repository Management</h1>
        <p className="page-subtitle">
          Connect and continuously monitor GitHub repositories. The AI assistant automatically evaluates pull requests as soon as they are opened.
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
            <span className="active-label">Actively Monitored ({monitoredRepos.length}):</span>
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

      {/* Connected Repositories Grid */}
      <div className="connected-repos-section">
        <h3 className="section-label-header">YOUR CONNECTED GITHUB REPOSITORIES</h3>
        {userRepos.length === 0 ? (
          <div className="empty-runs-state">
            <p>Loading repositories from connected GitHub account...</p>
          </div>
        ) : (
          <div className="repos-grid">
            {userRepos.map((repo) => (
              <div key={repo.id} className="repo-grid-card">
                <div className="repo-card-top">
                  <div className="repo-card-title-row">
                    <span className="repo-folder-icon">📁</span>
                    <h4 className="repo-card-name">{repo.name}</h4>
                  </div>
                  <span className="repo-card-branch">{repo.default_branch}</span>
                </div>

                <p className="repo-card-desc">
                  {repo.description || 'No description provided.'}
                </p>

                <div className="repo-card-meta">
                  <span className="repo-lang-chip">{repo.language}</span>
                  <span className="repo-stars-chip">⭐ {repo.stars}</span>
                </div>

                <div className="repo-card-actions">
                  <button
                    onClick={() => {
                      navigate(`/?repo=${encodeURIComponent(repo.full_name)}`);
                    }}
                    className="btn btn-secondary btn-sm w-full"
                  >
                    Select for Analysis
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
