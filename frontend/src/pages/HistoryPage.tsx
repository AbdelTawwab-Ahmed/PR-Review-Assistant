import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { StatusBadge } from '../components/StatusBadge';
import { StatsOverview } from '../components/StatsOverview';
import type { RunStatus } from '../types/run';

type FilterTab = 'all' | 'awaiting' | 'ready' | 'running';

export const HistoryPage: React.FC = () => {
  const [repoInput, setRepoInput] = useState('');
  const [prInput, setPrInput] = useState('');
  const [activeRepo, setActiveRepo] = useState<string | undefined>(undefined);
  const [activePr, setActivePr] = useState<number | undefined>(undefined);
  const [selectedTab, setSelectedTab] = useState<FilterTab>('all');

  const { data: runs, isLoading, error, refetch, isFetching } = useRuns(activeRepo, activePr);

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
    setSelectedTab('all');
  };

  const filteredRuns = useMemo(() => {
    if (!runs) return [];
    if (selectedTab === 'awaiting') {
      return runs.filter((r) => r.status === 'awaiting_approval');
    }
    if (selectedTab === 'ready') {
      return runs.filter((r) => r.status === 'ready_to_merge' || r.status === 'updating_pr');
    }
    if (selectedTab === 'running') {
      return runs.filter((r) =>
        ['analyzing', 'planning', 'fixing', 'validating', 'pending'].includes(r.status)
      );
    }
    return runs;
  }, [runs, selectedTab]);

  return (
    <div className="history-page">
      <div className="page-header-block">
        <h1 className="page-main-title">Analysis History</h1>
        <p className="page-subtitle">
          Historical log of all autonomous pull request analyses, security reviews, and human-in-the-loop decisions across repositories.
        </p>
      </div>

      <StatsOverview runs={runs || []} />

      {/* Control Bar: Tabs & Search */}
      <div className="control-bar-card">
        <div className="tab-pills">
          <button
            className={`tab-pill ${selectedTab === 'all' ? 'active' : ''}`}
            onClick={() => setSelectedTab('all')}
          >
            All Runs
            <span className="pill-count">{runs?.length || 0}</span>
          </button>
          <button
            className={`tab-pill ${selectedTab === 'awaiting' ? 'active' : ''}`}
            onClick={() => setSelectedTab('awaiting')}
          >
            <span className="tab-amber-dot" />
            Awaiting Approval
            <span className="pill-count count-amber">
              {runs?.filter((r) => r.status === 'awaiting_approval').length || 0}
            </span>
          </button>
          <button
            className={`tab-pill ${selectedTab === 'ready' ? 'active' : ''}`}
            onClick={() => setSelectedTab('ready')}
          >
            Ready to Merge
            <span className="pill-count count-emerald">
              {runs?.filter((r) => r.status === 'ready_to_merge').length || 0}
            </span>
          </button>
          <button
            className={`tab-pill ${selectedTab === 'running' ? 'active' : ''}`}
            onClick={() => setSelectedTab('running')}
          >
            Processing
            <span className="pill-count">
              {runs?.filter((r) => ['analyzing', 'planning', 'fixing', 'validating'].includes(r.status)).length || 0}
            </span>
          </button>
        </div>

        <form onSubmit={handleSearch} className="quick-search-form">
          <div className="search-input-wrap">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              placeholder="Filter by owner/repo..."
              value={repoInput}
              onChange={(e) => setRepoInput(e.target.value)}
              className="quick-search-input"
            />
          </div>

          <div className="pr-input-wrap">
            <span className="pr-hash">#</span>
            <input
              type="number"
              placeholder="PR"
              value={prInput}
              onChange={(e) => setPrInput(e.target.value)}
              className="quick-pr-input"
            />
          </div>

          <button type="submit" className="btn btn-primary btn-sm">
            Filter
          </button>

          {(activeRepo || activePr || selectedTab !== 'all') && (
            <button type="button" onClick={handleReset} className="btn btn-text btn-sm">
              Reset
            </button>
          )}

          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn btn-secondary btn-sm"
          >
            {isFetching ? 'Refreshing...' : 'Refresh'}
          </button>
        </form>
      </div>

      {isLoading && (
        <div className="glass-loading-state">
          <div className="spinner large" />
          <p className="loading-label">Loading history records from Azure PostgreSQL...</p>
        </div>
      )}

      {error && (
        <div className="alert-error-card">
          <div className="alert-icon">⚠️</div>
          <div className="alert-text">{(error as Error).message}</div>
        </div>
      )}

      {!isLoading && !error && filteredRuns.length === 0 && (
        <div className="empty-runs-card">
          <h4>No Reviews Found</h4>
          <p>No historical runs match the current criteria.</p>
        </div>
      )}

      {!isLoading && !error && filteredRuns.length > 0 && (
        <div className="runs-table-container">
          <table className="modern-table">
            <thead>
              <tr>
                <th>Repository & Pull Request</th>
                <th>Run Identifier</th>
                <th>Status</th>
                <th>Risk Score</th>
                <th>Findings</th>
                <th>Commit SHA</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run) => (
                <tr key={run.id} className="table-row">
                  <td>
                    <div className="repo-cell">
                      <Link to={`/runs/${encodeURIComponent(run.id)}`} className="repo-link">
                        <span className="repo-owner">{run.repo_full_name.split('/')[0]}</span>
                        <span className="repo-slash">/</span>
                        <span className="repo-name-bold">{run.repo_full_name.split('/')[1] || run.repo_full_name}</span>
                      </Link>
                      <span className="pr-tag">#{run.pr_number}</span>
                    </div>
                  </td>
                  <td>
                    <code className="code-chip">{run.id.slice(0, 8)}...</code>
                  </td>
                  <td>
                    <StatusBadge status={run.status as RunStatus} />
                  </td>
                  <td>
                    {run.risk ? (
                      <span className={`score-chip score-${run.risk.score > 65 ? 'high' : run.risk.score > 30 ? 'medium' : 'low'}`}>
                        {run.risk.score}/100
                      </span>
                    ) : (
                      <span className="text-dim">—</span>
                    )}
                  </td>
                  <td>
                    <span className="findings-count-badge">
                      {run.findings?.length || 0} findings
                    </span>
                  </td>
                  <td>
                    <code className="commit-chip">{run.head_sha.slice(0, 7)}</code>
                  </td>
                  <td className="text-right">
                    <Link to={`/runs/${encodeURIComponent(run.id)}`} className="btn btn-secondary btn-sm">
                      Inspect
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
