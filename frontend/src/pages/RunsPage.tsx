import React, { useState, useMemo, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { triggerRun } from '../api/runs';
import { getListeningRepos, startListeningRepo, stopListeningRepo } from '../api/repos';
import { StatusBadge } from '../components/StatusBadge';
import { StatsOverview } from '../components/StatsOverview';
import type { RunStatus } from '../types/run';

type FilterTab = 'all' | 'awaiting' | 'ready' | 'running';

function parsePrUrl(input: string): { repo: string; prNumber: number } | null {
  const trimmed = input.trim();
  const urlMatch = trimmed.match(/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/i);
  if (urlMatch) {
    return { repo: `${urlMatch[1]}/${urlMatch[2]}`, prNumber: parseInt(urlMatch[3], 10) };
  }
  const shortMatch = trimmed.match(/^([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)(?:#|\/pull\/)(\d+)$/i);
  if (shortMatch) {
    return { repo: `${shortMatch[1]}/${shortMatch[2]}`, prNumber: parseInt(shortMatch[3], 10) };
  }
  return null;
}

export const RunsPage: React.FC = () => {
  const [repoInput, setRepoInput] = useState('');
  const [prInput, setPrInput] = useState('');

  const [activeRepo, setActiveRepo] = useState<string | undefined>(undefined);
  const [activePr, setActivePr] = useState<number | undefined>(undefined);
  const [selectedTab, setSelectedTab] = useState<FilterTab>('all');

  // Trigger any PR state
  const [triggerUrl, setTriggerUrl] = useState('');
  const [isTriggering, setIsTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<{ type: 'success' | 'error'; text: string; link?: string } | null>(null);

  // Repository Listener State
  const [repoListenInput, setRepoListenInput] = useState('');
  const [isListeningLoading, setIsListeningLoading] = useState(false);
  const [monitoredRepos, setMonitoredRepos] = useState<string[]>([]);
  const [listenMsg, setListenMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const { data: runs, isLoading, error, refetch, isFetching } = useRuns(activeRepo, activePr);

  // Load monitored repositories on mount
  useEffect(() => {
    getListeningRepos()
      .then((res) => setMonitoredRepos(res.repositories))
      .catch(() => {});
  }, []);

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

  const handleTriggerAnyPr = async (e: React.FormEvent) => {
    e.preventDefault();
    setTriggerMsg(null);
    const parsed = parsePrUrl(triggerUrl);
    if (!parsed) {
      setTriggerMsg({
        type: 'error',
        text: 'Invalid format. Please enter a full GitHub PR URL (e.g. https://github.com/owner/repo/pull/123) or owner/repo#123',
      });
      return;
    }

    try {
      setIsTriggering(true);
      const res = await triggerRun(parsed.repo, parsed.prNumber);
      setTriggerMsg({
        type: 'success',
        text: `Analysis launched for ${parsed.repo} #${parsed.prNumber}! Multi-agent workflow running.`,
        link: res.dashboard_url,
      });
      setTriggerUrl('');
      setTimeout(() => refetch(), 1000);
    } catch (err: any) {
      setTriggerMsg({
        type: 'error',
        text: err?.message || 'Failed to trigger PR review. Ensure repository is accessible.',
      });
    } finally {
      setIsTriggering(false);
    }
  };

  const handleStartListening = async (e: React.FormEvent) => {
    e.preventDefault();
    setListenMsg(null);
    if (!repoListenInput.trim()) return;

    try {
      setIsListeningLoading(true);
      const res = await startListeningRepo(repoListenInput.trim());
      setListenMsg({
        type: 'success',
        text: res.message,
      });
      setRepoListenInput('');
      const updated = await getListeningRepos();
      setMonitoredRepos(updated.repositories);
      refetch();
    } catch (err: any) {
      setListenMsg({
        type: 'error',
        text: err?.message || 'Failed to listen to repository.',
      });
    } finally {
      setIsListeningLoading(false);
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

      {/* Repository Listener Card (Continuous Monitoring) */}
      <div className="analyze-pr-card">
        <div className="analyze-pr-header">
          <div className="analyze-pr-badge listener-badge">
            <span className="pulse-green-dot" />
            Active Repository Listener
          </div>
          <h3 className="analyze-pr-title">Listen for Any Pull Request on Any Repository</h3>
          <p className="analyze-pr-subtitle">
            Provide any repository URL (e.g. <code>https://github.com/AbdelTawwab-Ahmed/pr-test</code>). The assistant will automatically listen for every pull request opened or updated, and immediately review it.
          </p>
        </div>

        <form onSubmit={handleStartListening} className="analyze-pr-form">
          <div className="analyze-input-wrap">
            <svg className="github-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
            </svg>
            <input
              type="text"
              placeholder="Enter repo link (e.g. https://github.com/owner/repo or owner/repo)"
              value={repoListenInput}
              onChange={(e) => setRepoListenInput(e.target.value)}
              className="analyze-pr-input"
              disabled={isListeningLoading}
            />
          </div>
          <button type="submit" disabled={isListeningLoading || !repoListenInput.trim()} className="btn btn-primary analyze-submit-btn">
            {isListeningLoading ? (
              <>
                <div className="spinner small" />
                <span>Connecting...</span>
              </>
            ) : (
              <>
                <span>🎧 Start Listening</span>
              </>
            )}
          </button>
        </form>

        {listenMsg && (
          <div className={`analyze-pr-msg ${listenMsg.type}`}>
            <span>{listenMsg.text}</span>
          </div>
        )}

        {/* Monitored Repositories List */}
        {monitoredRepos.length > 0 && (
          <div className="monitored-repos-container">
            <span className="monitored-title">Currently Listening To ({monitoredRepos.length}):</span>
            <div className="monitored-chips">
              {monitoredRepos.map((repo) => (
                <div key={repo} className="monitored-chip">
                  <span className="pulse-green-dot small" />
                  <span className="chip-repo-name">{repo}</span>
                  <button
                    onClick={() => handleStopListening(repo)}
                    className="chip-remove-btn"
                    title="Stop listening to this repository"
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Direct Single PR Link Analyzer */}
      <div className="analyze-single-pr-bar">
        <form onSubmit={handleTriggerAnyPr} className="analyze-single-form">
          <span className="single-pr-label">⚡ Direct PR Review:</span>
          <input
            type="text"
            placeholder="Paste PR URL: https://github.com/owner/repo/pull/123"
            value={triggerUrl}
            onChange={(e) => setTriggerUrl(e.target.value)}
            className="single-pr-input"
            disabled={isTriggering}
          />
          <button type="submit" disabled={isTriggering || !triggerUrl.trim()} className="btn btn-secondary btn-sm">
            {isTriggering ? 'Analyzing...' : 'Run Review'}
          </button>
        </form>
        {triggerMsg && (
          <div className={`analyze-pr-msg ${triggerMsg.type} compact-msg`}>
            <span>{triggerMsg.text}</span>
            {triggerMsg.link && (
              <Link to={triggerMsg.link} className="view-run-btn">
                View &rarr;
              </Link>
            )}
          </div>
        )}
      </div>

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
        <div className="alert-error-card">
          <div className="alert-icon">⚠️</div>
          <div className="alert-text">
            <strong>Failed to connect with Backend:</strong> {(error as Error).message}
          </div>
          <button onClick={() => refetch()} className="btn btn-secondary btn-sm">
            Retry Connection
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && filteredRuns.length === 0 && (
        <div className="empty-runs-card">
          <div className="empty-icon-wrap">
            <div className="empty-icon-circle">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
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
              : 'Add any repository above to start listening for pull requests in real time.'}
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
                      <span className={`findings-pill ${findingsCount > 0 ? 'has-findings' : 'zero-findings'}`}>
                        {findingsCount} {findingsCount === 1 ? 'finding' : 'findings'}
                      </span>
                    </td>

                    <td>
                      <code className="commit-chip">{run.head_sha.slice(0, 7)}</code>
                    </td>

                    <td className="text-right">
                      <Link to={`/runs/${runId}`} className="btn btn-secondary btn-sm">
                        Inspect
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
