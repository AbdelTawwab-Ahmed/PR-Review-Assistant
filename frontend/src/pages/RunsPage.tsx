import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { StatusBadge } from '../components/StatusBadge';
import { StatsOverview } from '../components/StatsOverview';
import type { RunStatus } from '../types/run';

type FilterTab = 'all' | 'awaiting' | 'ready' | 'running';

export const RunsPage: React.FC = () => {
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
    <div className="page-container">
      {/* Top Hero Section */}
      <div className="hero-banner">
        <div className="hero-content">
          <div className="hero-pill">
            <span className="hero-sparkle">⚡</span> Multi-Agent LangGraph Intelligence
          </div>
          <h1 className="hero-title">Pull Request Review Intelligence</h1>
          <p className="hero-subtitle">
            Autonomous static security auditing, blast radius risk calculation, and multi-agent code fixes with Human-in-the-Loop authorization.
          </p>
        </div>
        <div className="hero-actions">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className={`btn btn-secondary ${isFetching ? 'loading' : ''}`}
          >
            <svg
              className={isFetching ? 'spin' : ''}
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l6.71-1.19" />
            </svg>
            {isFetching ? 'Syncing...' : 'Sync Cloud'}
          </button>
        </div>
      </div>

      {/* KPI Stats Overview Cards */}
      <StatsOverview runs={runs || []} />

      {/* Search and Tabs Toolbar */}
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
        </form>
      </div>

      {/* Main Content Area */}
      {isLoading && (
        <div className="glass-loading-state">
          <div className="spinner large" />
          <p className="loading-label">Fetching review runs from Azure PostgreSQL...</p>
        </div>
      )}

      {error && (
        <div className="error-glass-card">
          <div className="error-icon-box">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div>
            <h4 className="error-title">Database Query Interrupted</h4>
            <p className="error-desc">{(error as Error).message}</p>
          </div>
          <button onClick={() => refetch()} className="btn btn-secondary btn-sm ml-auto">
            Retry
          </button>
        </div>
      )}

      {!isLoading && !error && filteredRuns.length === 0 && (
        <div className="empty-glass-state">
          <div className="empty-illustration">
            <div className="empty-circle-glow">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="18" cy="18" r="3" />
                <circle cx="6" cy="6" r="3" />
                <path d="M13 6h3a2 2 0 0 1 2 2v7" />
                <line x1="6" y1="9" x2="6" y2="21" />
              </svg>
            </div>
          </div>
          <h3 className="empty-title">
            {runs && runs.length > 0 ? 'No matching reviews found' : 'Ready for your first Pull Request'}
          </h3>
          <p className="empty-desc">
            {runs && runs.length > 0
              ? 'Try modifying your filter parameters or clearing the search.'
              : 'When a Pull Request is opened or updated on GitHub, Azure App Service triggers the LangGraph agent swarm to analyze code changes in real time.'}
          </p>
          {(!runs || runs.length === 0) && (
            <div className="empty-webhook-hint">
              <span className="webhook-badge">Webhook Endpoint</span>
              <code>https://gpgai2-ghdvf7b6caetf3ds.westus3-01.azurewebsites.net/api/webhooks/github</code>
            </div>
          )}
        </div>
      )}

      {/* Table of Review Runs */}
      {!isLoading && !error && filteredRuns.length > 0 && (
        <div className="runs-table-container">
          <table className="modern-table">
            <thead>
              <tr>
                <th>Repository & Pull Request</th>
                <th>Run Identifier</th>
                <th>Workflow Status</th>
                <th>Risk Score</th>
                <th>Findings</th>
                <th>Commit SHA</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run) => {
                const runId = run.id;
                const riskScore = run.risk?.score;
                const findingsCount = run.findings?.length || 0;
                const isAwaiting = run.status === 'awaiting_approval';

                return (
                  <tr key={runId} className={`table-row ${isAwaiting ? 'row-highlight' : ''}`}>
                    <td>
                      <div className="repo-cell">
                        <Link to={`/runs/${runId}`} className="repo-link">
                          <span className="repo-owner">{run.repo_full_name.split('/')[0]}</span>
                          <span className="repo-slash">/</span>
                          <span className="repo-name-bold">{run.repo_full_name.split('/')[1] || run.repo_full_name}</span>
                        </Link>
                        <span className="pr-tag">#{run.pr_number}</span>
                      </div>
                    </td>

                    <td>
                      <code className="code-chip" title={runId}>
                        {runId.slice(0, 8)}...
                      </code>
                    </td>

                    <td>
                      <StatusBadge status={run.status as RunStatus} />
                    </td>

                    <td>
                      {riskScore !== undefined ? (
                        <div className="score-badge-wrap">
                          <div
                            className={`score-pill ${
                              riskScore > 65 ? 'score-high' : riskScore > 30 ? 'score-medium' : 'score-low'
                            }`}
                          >
                            <span className="score-num">{riskScore}</span>
                            <span className="score-denom">/100</span>
                          </div>
                        </div>
                      ) : (
                        <span className="text-dim">—</span>
                      )}
                    </td>

                    <td>
                      {findingsCount > 0 ? (
                        <span className="findings-chip">
                          <span className="findings-count-num">{findingsCount}</span> issues
                        </span>
                      ) : (
                        <span className="clean-chip">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          Clean
                        </span>
                      )}
                    </td>

                    <td>
                      <span className="sha-badge">{run.head_sha.slice(0, 7)}</span>
                    </td>

                    <td className="text-right">
                      <Link
                        to={`/runs/${runId}`}
                        className={`btn btn-sm ${isAwaiting ? 'btn-amber-glow' : 'btn-ghost'}`}
                      >
                        {isAwaiting ? 'Authorize' : 'View Run'}
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <polyline points="9 18 15 12 9 6" />
                        </svg>
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
