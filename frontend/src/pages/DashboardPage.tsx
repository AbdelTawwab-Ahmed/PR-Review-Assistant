import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { analyzeRepository } from '../api/repos';
import { RepoSelector } from '../components/RepoSelector';
import { LiveAnalysisTracker } from '../components/LiveAnalysisTracker';
import { StatsOverview } from '../components/StatsOverview';
import { StatusBadge } from '../components/StatusBadge';
import { RiskGauge } from '../components/RiskGauge';
import { FindingsList } from '../components/FindingsList';
import { DiffViewer } from '../components/DiffViewer';
import type { RunDetail, RunStatus } from '../types/run';

export const DashboardPage: React.FC = () => {
  const { data: runs, isLoading: isRunsLoading, refetch } = useRuns();

  const trackerRef = React.useRef<HTMLDivElement>(null);
  const [activeAnalysis, setActiveAnalysis] = useState<{
    runId: string;
    repo: string;
    prNumber: number;
  } | null>(null);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [completedRun, setCompletedRun] = useState<RunDetail | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const handleStartAnalyze = async (repo: string, prNumber?: number) => {
    setAnalysisError(null);
    setCompletedRun(null);
    setIsAnalyzing(true);
    setActiveAnalysis({
      runId: '',
      repo,
      prNumber: prNumber || 1,
    });

    // Smoothly reveal and scroll directly to the analysis tracker
    setTimeout(() => {
      trackerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 60);

    try {
      const res = await analyzeRepository(repo, prNumber);
      setActiveAnalysis({
        runId: res.run_id,
        repo: res.repo,
        prNumber: res.pr_number,
      });
    } catch (err: any) {
      setAnalysisError(err?.message || 'Failed to trigger repository analysis. Check repository accessibility.');
      setIsAnalyzing(false);
      setActiveAnalysis(null);
    }
  };

  const handleAnalysisCompleted = (detail: RunDetail) => {
    setIsAnalyzing(false);
    setCompletedRun(detail);
    refetch();
  };

  return (
    <div className="dashboard-page">
      {/* Platform Hero Banner */}
      <div className="dashboard-hero">
        <div className="hero-left">
          <div className="hero-pill-tag">
            <span className="sparkle-icon">✨</span>
            <span>Enterprise Multi-Agent Code Intelligence</span>
          </div>
          <h1 className="hero-main-title">AI-Powered Pull Request & Code Review</h1>
          <p className="hero-main-desc">
            Connect any GitHub repository to orchestrate autonomous AI agents specialized in static analysis, bug detection, blast radius assessment, and Human-in-the-Loop automated fixes.
          </p>
        </div>
      </div>

      {/* 1. Repository Selection Section */}
      <RepoSelector onAnalyze={handleStartAnalyze} isAnalyzing={isAnalyzing} />

      {analysisError && (
        <div className="dashboard-alert-error">
          <span className="alert-icon">⚠️</span>
          <span>{analysisError}</span>
        </div>
      )}

      {/* 2. Repository Analysis Workflow (Live Real-Time Stepper) */}
      {activeAnalysis && isAnalyzing && (
        <div ref={trackerRef}>
          <LiveAnalysisTracker
            runId={activeAnalysis.runId}
            repo={activeAnalysis.repo}
            prNumber={activeAnalysis.prNumber}
            onAnalysisCompleted={handleAnalysisCompleted}
          />
        </div>
      )}

      {/* 3. Revealed Completed Analysis Dashboard */}
      {completedRun && (
        <section className="completed-analysis-reveal">
          <div className="reveal-header">
            <div className="reveal-title-wrap">
              <span className="reveal-badge">✓ Analysis Complete</span>
              <h3 className="reveal-title">
                Review Results: {completedRun.repo_full_name} #{completedRun.pr_number}
              </h3>
            </div>
            <Link to={`/runs/${encodeURIComponent(completedRun.run_id)}`} className="btn btn-primary btn-sm">
              Open Full Review Workspace &rarr;
            </Link>
          </div>

          <div className="reveal-grid">
            {/* Risk Gauge Card */}
            {completedRun.risk && (
              <div className="reveal-card">
                <h4 className="card-heading">Risk Score & Assessment</h4>
                <RiskGauge risk={completedRun.risk} />
              </div>
            )}

            {/* Findings Card */}
            <div className="reveal-card">
              <h4 className="card-heading">Detected Findings ({completedRun.findings?.length || 0})</h4>
              <FindingsList findings={completedRun.findings || []} />
            </div>
          </div>

          {/* AI Proposed Fix Diff */}
          {completedRun.proposal && completedRun.proposal.changes && completedRun.proposal.changes.length > 0 && (
            <div className="reveal-card full-width">
              <div className="card-header-flex">
                <h4 className="card-heading">💡 AI Generated Fix Proposal</h4>
                <span className="fix-summary-pill">{completedRun.proposal.summary || completedRun.proposal.plan_summary || 'Automated Fix'}</span>
              </div>
              <DiffViewer changes={completedRun.proposal.changes} />
            </div>
          )}
        </section>
      )}

      {/* KPI Stats Overview */}
      <div className="dashboard-stats-wrapper">
        <h3 className="section-label-header">SYSTEM OVERVIEW</h3>
        <StatsOverview runs={runs || []} />
      </div>

      {/* Recent Analysis Runs Table */}
      <section className="dashboard-recent-section">
        <div className="section-header-flex">
          <h3 className="section-label-header">RECENT REPOSITORY REVIEWS</h3>
          <Link to="/history" className="view-all-link">
            View All History &rarr;
          </Link>
        </div>

        {isRunsLoading ? (
          <div className="glass-loading-state">
            <div className="spinner" />
            <p className="loading-label">Fetching review history...</p>
          </div>
        ) : !runs || runs.length === 0 ? (
          <div className="empty-runs-state">
            <div className="empty-icon-circle">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <h4>No Repository Reviews Yet</h4>
            <p>Paste any GitHub repository URL above and click <strong>Analyze Repository</strong> to start your first multi-agent review.</p>
          </div>
        ) : (
          <div className="runs-table-container">
            <table className="modern-table">
              <thead>
                <tr>
                  <th>Repository & PR</th>
                  <th>Status</th>
                  <th>Risk Score</th>
                  <th>Findings</th>
                  <th>Commit</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 8).map((r) => (
                  <tr key={r.id} className="table-row">
                    <td>
                      <div className="repo-cell">
                        <Link to={`/runs/${encodeURIComponent(r.id)}`} className="repo-link">
                          <span className="repo-owner">{r.repo_full_name.split('/')[0]}</span>
                          <span className="repo-slash">/</span>
                          <span className="repo-name-bold">{r.repo_full_name.split('/')[1] || r.repo_full_name}</span>
                        </Link>
                        <span className="pr-tag">#{r.pr_number}</span>
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={r.status as RunStatus} />
                    </td>
                    <td>
                      {r.risk ? (
                        <span className={`score-chip score-${r.risk.score > 65 ? 'high' : r.risk.score > 30 ? 'medium' : 'low'}`}>
                          {r.risk.score}/100
                        </span>
                      ) : (
                        <span className="text-dim">—</span>
                      )}
                    </td>
                    <td>
                      <span className="findings-count-badge">
                        {r.findings?.length || 0} findings
                      </span>
                    </td>
                    <td>
                      <code className="commit-chip">{r.head_sha.slice(0, 7)}</code>
                    </td>
                    <td className="text-right">
                      <Link to={`/runs/${encodeURIComponent(r.id)}`} className="btn btn-secondary btn-sm">
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
