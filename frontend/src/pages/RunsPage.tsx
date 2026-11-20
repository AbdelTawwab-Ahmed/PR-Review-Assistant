import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { StatusBadge } from '../components/StatusBadge';

export const RunsPage: React.FC = () => {
  const [repoInput, setRepoInput] = useState('');
  const [prInput, setPrInput] = useState('');

  const [activeRepo, setActiveRepo] = useState<string | undefined>(undefined);
  const [activePr, setActivePr] = useState<number | undefined>(undefined);

  const { data: runs, isLoading, error, refetch } = useRuns(activeRepo, activePr);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setActiveRepo(repoInput.trim() || undefined);
    setActivePr(prInput.trim() ? parseInt(prInput.trim(), 10) : undefined);
  };

  const handleReset = () => {
    setRepoInput('');
    setPrInput('');
    setActiveRepo(undefined);
    setActivePr(undefined);
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Pull Request Review Runs</h1>
          <p className="page-subtitle">
            Autonomous multi-agent code analysis, security auditing, and automated fixes
          </p>
        </div>
        <button onClick={() => refetch()} className="btn btn-secondary btn-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l6.71-1.19" />
          </svg>
          Refresh
        </button>
      </div>

      <div className="filter-card">
        <form onSubmit={handleSearch} className="filter-form">
          <div className="input-group">
            <label className="input-label">Repository</label>
            <input
              type="text"
              placeholder="e.g. owner/repo"
              value={repoInput}
              onChange={(e) => setRepoInput(e.target.value)}
              className="text-input"
            />
          </div>

          <div className="input-group">
            <label className="input-label">PR Number</label>
            <input
              type="number"
              placeholder="e.g. 42"
              value={prInput}
              onChange={(e) => setPrInput(e.target.value)}
              className="text-input"
            />
          </div>

          <div className="filter-actions">
            <button type="submit" className="btn btn-primary">
              Filter Runs
            </button>
            {(activeRepo || activePr) && (
              <button type="button" onClick={handleReset} className="btn btn-text">
                Clear Filter
              </button>
            )}
          </div>
        </form>
      </div>

      {isLoading && (
        <div className="loading-state">
          <div className="spinner large" />
          <p>Loading review runs...</p>
        </div>
      )}

      {error && (
        <div className="error-banner">
          <p>Failed to load runs: {(error as Error).message}</p>
        </div>
      )}

      {!isLoading && !error && (!runs || runs.length === 0) && (
        <div className="empty-state">
          <div className="empty-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h3>No review runs found</h3>
          <p>
            {activeRepo
              ? `No review runs recorded for ${activeRepo}.`
              : 'Enter a repository name above or trigger a PR webhook to see active runs.'}
          </p>
        </div>
      )}

      {!isLoading && !error && runs && runs.length > 0 && (
        <div className="table-card">
          <table className="runs-table">
            <thead>
              <tr>
                <th>Repository</th>
                <th>PR #</th>
                <th>Commit SHA</th>
                <th>Status</th>
                <th>Risk Score</th>
                <th>Last Updated</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="run-row">
                  <td className="repo-cell">
                    <span className="repo-name">{run.repo_full_name}</span>
                  </td>
                  <td>
                    <span className="pr-number">#{run.pr_number}</span>
                  </td>
                  <td>
                    <code className="sha-code">{run.head_sha.slice(0, 7)}</code>
                  </td>
                  <td>
                    <StatusBadge status={run.status} size="sm" />
                  </td>
                  <td>
                    {run.risk ? (
                      <span className={`risk-pill level-${run.risk.level.toLowerCase()}`}>
                        {run.risk.score} / 100
                      </span>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="date-cell">
                    {new Date(run.updated_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </td>
                  <td>
                    <Link to={`/runs/${run.id}`} className="view-link">
                      View Details &rarr;
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
