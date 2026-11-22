import React, { useState } from 'react';
import { useParams, useLocation, Link } from 'react-router-dom';
import { useRun, useApproveRun } from '../hooks/useRuns';
import { triggerRun } from '../api/runs';
import { StatusBadge } from '../components/StatusBadge';
import { RiskGauge } from '../components/RiskGauge';
import { DiffViewer } from '../components/DiffViewer';
import { FindingsList } from '../components/FindingsList';
import { ApprovalModal } from '../components/ApprovalModal';
import { AgentPipeline } from '../components/AgentPipeline';
import type { ApprovalDecision, RunStatus } from '../types/run';

export const RunDetailPage: React.FC = () => {
  const params = useParams<{ runId?: string; '*': string }>();
  const location = useLocation();

  // Extract runId reliably even if it contains slashes (/), hashes (#), or encoded chars
  const rawId = params['*'] || params.runId || location.pathname.replace(/^\/runs\/?/, '');
  const fullRaw = rawId + (location.hash || '');
  const runId = decodeURIComponent(fullRaw);

  const { data: run, isLoading, error, refetch, isFetching } = useRun(runId);
  const approveMutation = useApproveRun(runId || '');

  const [activeTab, setActiveTab] = useState<'proposal' | 'findings' | 'risk' | 'notes'>('proposal');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalStage, setModalStage] = useState<'plan' | 'final'>('final');
  const [actionError, setActionError] = useState<string | null>(null);
  const [copiedSha, setCopiedSha] = useState(false);
  const [isRerunning, setIsRerunning] = useState(false);

  const handleRerun = async () => {
    if (!run) return;
    setIsRerunning(true);
    setActionError(null);
    try {
      await triggerRun(run.repo_full_name, run.pr_number);
      setTimeout(() => refetch(), 1500);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to trigger re-run');
    } finally {
      setIsRerunning(false);
    }
  };

  React.useEffect(() => {
    if (run?.status === 'awaiting_plan_approval') {
      setActiveTab('findings');
    }
  }, [run?.status]);

  const handleApprovalSubmit = async (decision: ApprovalDecision, feedback: string) => {
    setActionError(null);
    try {
      await approveMutation.mutateAsync({ decision, feedback });
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const copySha = () => {
    if (run?.head_sha) {
      navigator.clipboard.writeText(run.head_sha);
      setCopiedSha(true);
      setTimeout(() => setCopiedSha(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <div className="page-container">
        <div className="glass-loading-state">
          <div className="spinner large" />
          <p className="loading-label">Loading agent state and execution artifacts...</p>
        </div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="page-container">
        <div className="error-glass-card">
          <div className="error-icon-box">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div>
            <h4 className="error-title">Review Run Not Found</h4>
            <p className="error-desc">{(error as Error)?.message || 'Unable to locate run records in database.'}</p>
          </div>
          <Link to="/" className="btn btn-secondary btn-sm ml-auto">
            &larr; Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const isAwaitingPlan = run.status === 'awaiting_plan_approval';
  const isAwaitingFinal = run.status === 'awaiting_approval';
  const isClean = run.status === 'ready_to_merge' && (!run.findings_count || run.findings_count === 0);
  const findingsCount = run.findings_count || run.findings?.length || 0;
  const fileChangesCount = run.proposal?.changes?.length || 0;

  return (
    <div className="page-container">
      {/* Breadcrumb Navigation */}
      <div className="breadcrumbs-bar">
        <Link to="/" className="crumb-home">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          Dashboard
        </Link>
        <span className="crumb-arrow">/</span>
        <span className="crumb-repo">{run.repo_full_name}</span>
        <span className="crumb-arrow">/</span>
        <span className="crumb-active">PR #{run.pr_number}</span>
      </div>

      {/* Hero Header Card */}
      <div className="run-detail-header-card">
        <div className="detail-header-main">
          <div className="title-row">
            <h1 className="detail-heading">
              {run.repo_full_name} <span className="highlight-pr-tag">#{run.pr_number}</span>
            </h1>
            <a
              href={`https://github.com/${run.repo_full_name}/pull/${run.pr_number}`}
              target="_blank"
              rel="noopener noreferrer"
              className="github-pr-link-btn"
              title="Open Pull Request on GitHub"
            >
              GitHub PR
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
          </div>

          <div className="meta-chips-row">
            <div className="meta-chip">
              <span className="meta-chip-label">Run ID</span>
              <code className="meta-chip-value">{run.run_id}</code>
            </div>

            <div className="meta-chip clickable-chip" onClick={copySha} title="Click to copy commit SHA">
              <span className="meta-chip-label">Commit</span>
              <code className="meta-chip-value">{(run.head_sha || '').slice(0, 8) || 'HEAD'}</code>
              <span className="copy-label">{copiedSha ? 'Copied!' : 'Copy'}</span>
            </div>

            {run.risk && run.risk.level && (
              <div className="meta-chip">
                <span className="meta-chip-label">Risk Level</span>
                <span className={`risk-pill-text level-${String(run.risk.level).toLowerCase()}`}>
                  {String(run.risk.level).toUpperCase()} ({run.risk.score ?? 0}/100)
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="detail-header-side">
          <StatusBadge status={run.status as RunStatus} size="lg" />
          <button
            onClick={handleRerun}
            disabled={isRerunning}
            className="btn btn-primary btn-sm"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
            title="Trigger a fresh autonomous review of this PR"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            {isRerunning ? 'Triggering...' : 'Re-run Review'}
          </button>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn btn-secondary btn-icon-only"
            title="Refresh State"
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
          </button>
        </div>
      </div>

      {/* Interactive LangGraph Agent Pipeline */}
      <AgentPipeline status={run.status as RunStatus} />

      {/* Clean Repository Success State */}
      {isClean && (
        <div className="hitl-banner-elevated" style={{ borderColor: 'rgba(16, 185, 129, 0.4)', background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(6, 78, 59, 0.15))' }}>
          <div className="hitl-badge-pulse" style={{ background: 'rgba(16, 185, 129, 0.15)' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <div className="hitl-content">
            <h3 className="hitl-headline" style={{ color: '#10B981' }}>Repository Is Clean — No Issues Detected</h3>
            <p className="hitl-body">
              The multi-agent inspection concluded successfully. No security vulnerabilities, logic defects, or high-risk problems were identified. Workflow terminated cleanly with zero modifications needed.
            </p>
          </div>
        </div>
      )}

      {/* Stage 1: Initial Remediation Authorization Gate */}
      {isAwaitingPlan && (
        <div className="hitl-banner-elevated">
          <div className="hitl-glow-orb" />
          <div className="hitl-badge-pulse">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2.2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div className="hitl-content">
            <h3 className="hitl-headline">Gate 1: Remediation Authorization Required</h3>
            <p className="hitl-body">
              The agent has inspected the repository and detected {findingsCount} issue(s). <strong>Under strict HITL constraints, no code modifications have taken place.</strong> Review the detected issues below and authorize the remediation agents to formulate and test fixes.
            </p>
          </div>
          <button
            onClick={() => {
              setModalStage('plan');
              setIsModalOpen(true);
            }}
            className="btn btn-primary btn-authorize-glow"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Review & Authorize Remediation
          </button>
        </div>
      )}

      {/* Stage 2: Remediation Review Gate */}
      {isAwaitingFinal && (
        <div className="hitl-banner-elevated">
          <div className="hitl-glow-orb" />
          <div className="hitl-badge-pulse">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.2">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="hitl-content">
            <h3 className="hitl-headline">Gate 2: Remediation Review & PR Approval</h3>
            <p className="hitl-body">
              Remediation agents formulated patches and validated them with test suites in an isolated sandbox. Review the side-by-side diff below and authorize creating a Pull Request on GitHub.
            </p>
          </div>
          <button
            onClick={() => {
              setModalStage('final');
              setIsModalOpen(true);
            }}
            className="btn btn-primary btn-authorize-glow"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Review & Publish PR
          </button>
        </div>
      )}

      {actionError && (
        <div className="error-glass-card mt-4">
          <p className="error-desc">Action failed: {actionError}</p>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="detail-tabs-bar">
        <button
          className={`detail-tab ${activeTab === 'proposal' ? 'active' : ''}`}
          onClick={() => setActiveTab('proposal')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          Fix Proposal
          {fileChangesCount > 0 && <span className="tab-count-chip">{fileChangesCount} files</span>}
        </button>

        <button
          className={`detail-tab ${activeTab === 'findings' ? 'active' : ''}`}
          onClick={() => setActiveTab('findings')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          Audit Findings
          {findingsCount > 0 && (
            <span className={`tab-count-chip ${findingsCount > 0 ? 'chip-amber' : ''}`}>
              {findingsCount}
            </span>
          )}
        </button>

        <button
          className={`detail-tab ${activeTab === 'risk' ? 'active' : ''}`}
          onClick={() => setActiveTab('risk')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
          Risk Assessment
        </button>

        <button
          className={`detail-tab ${activeTab === 'notes' ? 'active' : ''}`}
          onClick={() => setActiveTab('notes')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="8" y1="6" x2="21" y2="6" />
            <line x1="8" y1="12" x2="21" y2="12" />
            <line x1="8" y1="18" x2="21" y2="18" />
            <line x1="3" y1="6" x2="3.01" y2="6" />
            <line x1="3" y1="12" x2="3.01" y2="12" />
            <line x1="3" y1="18" x2="3.01" y2="18" />
          </svg>
          Review Notes
        </button>
      </div>

      {/* Tab Panels */}
      <div className="tab-panel-container">
        {activeTab === 'proposal' && (
          <div className="panel-proposal">
            {run.proposal && (
              <div className="fix-rationale-box">
                <div className="rationale-header">
                  <span className="agent-badge-tag">AI Fix Engine</span>
                  <span className="attempt-badge">Status: {run.proposal.status || 'Ready'}</span>
                </div>
                <h4 className="rationale-title">Optimization Rationale</h4>
                <p className="rationale-text">
                  {run.proposal.plan_summary || run.proposal.explanation || 'Autonomous code remediation proposed to resolve static analysis findings.'}
                </p>
              </div>
            )}

            <DiffViewer changes={run.proposal?.changes || []} />
          </div>
        )}

        {activeTab === 'findings' && (
          <FindingsList findings={run.findings || []} count={findingsCount} />
        )}

        {activeTab === 'risk' && (
          <RiskGauge risk={run.risk} />
        )}

        {activeTab === 'notes' && (
          <div className="notes-card">
            <h3 className="section-title">Reviewer & Agent Notes</h3>
            {run.notes && run.notes.length > 0 ? (
              <div className="markdown-prose">
                {run.notes.map((note, idx) => (
                  <pre key={idx} className="notes-pre">{note}</pre>
                ))}
              </div>
            ) : (
              <div className="notes-empty">
                <p>No extra review notes generated for this run.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal Dialog */}
      <ApprovalModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleApprovalSubmit}
        isLoading={approveMutation.isPending}
        stage={modalStage}
      />
    </div>
  );
};
