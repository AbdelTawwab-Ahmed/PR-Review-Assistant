import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useRun, useApproveRun } from '../hooks/useRuns';
import { StatusBadge } from '../components/StatusBadge';
import { RiskGauge } from '../components/RiskGauge';
import { DiffViewer } from '../components/DiffViewer';
import { FindingsList } from '../components/FindingsList';
import { ApprovalModal } from '../components/ApprovalModal';
import type { ApprovalDecision } from '../types/run';

export const RunDetailPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const { data: run, isLoading, error, refetch } = useRun(runId);
  const approveMutation = useApproveRun(runId || '');

  const [activeTab, setActiveTab] = useState<'proposal' | 'findings' | 'risk' | 'notes'>('proposal');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleApprovalSubmit = async (decision: ApprovalDecision, feedback: string) => {
    setActionError(null);
    try {
      await approveMutation.mutateAsync({ decision, feedback });
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  if (isLoading) {
    return (
      <div className="page-container loading-container">
        <div className="spinner large" />
        <p>Loading run details...</p>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="page-container">
        <div className="error-banner">
          <h3>Failed to load review run</h3>
          <p>{(error as Error)?.message || 'Run not found'}</p>
          <Link to="/" className="btn btn-secondary mt-4">
            &larr; Back to Runs
          </Link>
        </div>
      </div>
    );
  }

  const isAwaiting = run.status === 'awaiting_approval';

  return (
    <div className="page-container">
      <div className="breadcrumbs">
        <Link to="/" className="crumb-link">Runs</Link>
        <span className="crumb-sep">/</span>
        <span className="crumb-current">{run.repo_full_name} #{run.pr_number}</span>
      </div>

      <div className="detail-header-card">
        <div className="detail-header-top">
          <div className="detail-title-group">
            <h1 className="detail-title">
              {run.repo_full_name} <span className="highlight-pr">#{run.pr_number}</span>
            </h1>
            <div className="detail-meta">
              <span className="meta-item">
                <strong>Run ID:</strong> <code>{run.run_id}</code>
              </span>
              <span className="meta-sep">&bull;</span>
              <span className="meta-item">
                <strong>Head SHA:</strong> <code>{run.head_sha.slice(0, 7)}</code>
              </span>
            </div>
          </div>

          <div className="detail-status-group">
            <StatusBadge status={run.status} size="lg" />
            <button onClick={() => refetch()} className="btn btn-secondary btn-sm" title="Refresh">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l6.71-1.19" />
              </svg>
            </button>
          </div>
        </div>

        {isAwaiting && (
          <div className="hitl-banner">
            <div className="hitl-banner-content">
              <div className="hitl-pulse-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
              <div>
                <h4 className="hitl-banner-title">Human Authorization Required</h4>
                <p className="hitl-banner-desc">
                  The AI multi-agent workflow has verified fixes and requires your approval before publishing to GitHub.
                </p>
              </div>
            </div>
            <div className="hitl-banner-actions">
              <button
                onClick={() => setIsModalOpen(true)}
                className="btn btn-primary"
              >
                Review & Decide &rarr;
              </button>
            </div>
          </div>
        )}

        {run.published_pr_url && (
          <div className="published-banner">
            <div className="published-content">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
              <span>Fix PR published successfully to GitHub:</span>
            </div>
            <a
              href={run.published_pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="published-link"
            >
              Open Pull Request &rarr;
            </a>
          </div>
        )}

        {actionError && (
          <div className="error-banner">
            <p>Action failed: {actionError}</p>
          </div>
        )}
      </div>

      <div className="tab-navigation">
        <button
          onClick={() => setActiveTab('proposal')}
          className={`tab-btn ${activeTab === 'proposal' ? 'active' : ''}`}
        >
          Fix Proposals ({run.proposal?.changes?.length || 0})
        </button>
        <button
          onClick={() => setActiveTab('risk')}
          className={`tab-btn ${activeTab === 'risk' ? 'active' : ''}`}
        >
          Risk Assessment {run.risk && `(${run.risk.score}/100)`}
        </button>
        <button
          onClick={() => setActiveTab('findings')}
          className={`tab-btn ${activeTab === 'findings' ? 'active' : ''}`}
        >
          Findings ({run.findings_count})
        </button>
        <button
          onClick={() => setActiveTab('notes')}
          className={`tab-btn ${activeTab === 'notes' ? 'active' : ''}`}
        >
          Timeline & Notes ({run.notes?.length || 0})
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'proposal' && (
          <div className="tab-pane">
            {run.proposal ? (
              <div className="proposal-card">
                <div className="proposal-header">
                  <h3 className="section-title">Automated Fix Summary</h3>
                  <p className="proposal-summary">{run.proposal.plan_summary}</p>
                  {run.proposal.explanation && (
                    <div className="proposal-explanation">
                      <strong>Agent Explanation:</strong> {run.proposal.explanation}
                    </div>
                  )}
                </div>
                <DiffViewer changes={run.proposal.changes} />
              </div>
            ) : (
              <div className="empty-state">
                <p>No automated fix proposals generated for this run.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'risk' && (
          <div className="tab-pane">
            <RiskGauge risk={run.risk} />
          </div>
        )}

        {activeTab === 'findings' && (
          <div className="tab-pane">
            <FindingsList count={run.findings_count} />
          </div>
        )}

        {activeTab === 'notes' && (
          <div className="tab-pane">
            <div className="notes-card">
              <h3 className="section-title">Workflow Execution Notes</h3>
              {(!run.notes || run.notes.length === 0) ? (
                <p className="text-muted">No execution notes logged for this run.</p>
              ) : (
                <ul className="notes-list">
                  {run.notes.map((note, idx) => (
                    <li key={idx} className="note-item">
                      <span className="note-dot" />
                      <span className="note-text">{note}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>

      <ApprovalModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleApprovalSubmit}
        isLoading={approveMutation.isPending}
      />
    </div>
  );
};
