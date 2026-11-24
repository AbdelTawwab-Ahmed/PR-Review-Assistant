import React, { useState, useEffect } from 'react';
import { getRun, triggerRun } from '../api/runs';
import type { RunDetail } from '../types/run';

interface LiveAnalysisTrackerProps {
  runId: string;
  repo: string;
  prNumber: number;
  onAnalysisCompleted: (detail: RunDetail) => void;
}

interface StageInfo {
  id: string;
  title: string;
  agent: string;
  desc: string;
  icon: string;
}

const STAGES: StageInfo[] = [
  { id: 'clone', title: 'Repository Ingestion', agent: 'Context Loader', desc: 'Fetching files, branches & diff trees', icon: '📥' },
  { id: 'diff', title: 'Codebase Chunking', agent: 'AST Planner', desc: 'Chunking diffs & planning analysis strategy', icon: '📊' },
  { id: 'reviewer', title: 'Bug Detection', agent: 'Reviewer Agent', desc: 'Azure OpenAI GPT-4.1 identifying logic defects', icon: '🔍' },
  { id: 'security', title: 'Security Analysis', agent: 'Security Agent', desc: 'Scanning for OWASP & vulnerability vectors', icon: '🛡️' },
  { id: 'risk', title: 'Risk Assessment', agent: 'Risk Engine', desc: 'Calculating blast radius & file impact score', icon: '💥' },
  { id: 'fixer', title: 'AI Fix Generation', agent: 'Fixer Agent', desc: 'Synthesizing automated code patches', icon: '💡' },
  { id: 'review', title: 'AI Review Summary', agent: 'LangGraph Orchestrator', desc: 'Compiling executive review & HITL gate', icon: '📋' },
];

export const LiveAnalysisTracker: React.FC<LiveAnalysisTrackerProps> = ({
  runId,
  repo,
  prNumber,
  onAnalysisCompleted,
}) => {
  const [elapsed, setElapsed] = useState(0);
  const [currentRun, setCurrentRun] = useState<RunDetail | null>(null);
  const [isDone, setIsDone] = useState(false);
  const [pollError, setPollError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  // Timer
  useEffect(() => {
    if (isDone || pollError) return;
    const timer = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [isDone, pollError]);

  // Poll backend run status
  useEffect(() => {
    if (!runId) return;
    let isCancelled = false;
    let errorCount = 0;

    const poll = async () => {
      try {
        const detail = await getRun(runId);
        if (isCancelled) return;
        errorCount = 0;
        setPollError(null);
        setCurrentRun(detail);

        if (
          detail.status === 'awaiting_plan_approval' ||
          detail.status === 'awaiting_approval' ||
          detail.status === 'ready_to_merge' ||
          detail.status === 'rejected' ||
          detail.status === 'failed'
        ) {
          setIsDone(true);
          onAnalysisCompleted(detail);
        }
      } catch (err: unknown) {
        if (isCancelled) return;
        errorCount += 1;
        if (errorCount >= 10) {
          setPollError(
            err instanceof Error
              ? err.message
              : 'Analysis run was not found or was cancelled on the backend. Please re-analyze.'
          );
        }
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [runId, onAnalysisCompleted]);

  const handleRetryRun = async () => {
    setIsRetrying(true);
    try {
      await triggerRun(repo, prNumber);
      setPollError(null);
      setElapsed(0);
      window.location.reload();
    } catch (err: unknown) {
      setPollError(err instanceof Error ? err.message : 'Failed to re-trigger analysis');
    } finally {
      setIsRetrying(false);
    }
  };

  // Determine stage progress based on actual backend status
  const getStageState = (index: number): 'completed' | 'active' | 'pending' => {
    if (isDone) return 'completed';

    const status = currentRun?.status || 'analyzing';

    if (status === 'pending') {
      return index === 0 ? 'active' : 'pending';
    }
    if (status === 'analyzing') {
      // Parallel multi-threaded execution through the LangGraph agents
      if (elapsed < 6) {
        if (index === 0) return 'completed';
        if (index === 1) return 'active';
        return 'pending';
      } else if (elapsed < 24) {
        if (index < 2) return 'completed';
        // Both Bug Reviewer and Security agents run in parallel threads concurrently
        if (index === 2 || index === 3) return 'active';
        return 'pending';
      } else if (elapsed < 38) {
        if (index < 4) return 'completed';
        if (index === 4) return 'active';
        return 'pending';
      } else {
        if (index < 5) return 'completed';
        if (index === 5 || index === 6) return 'active';
        return 'pending';
      }
    }
    if (status === 'planning') {
      if (index < 4) return 'completed';
      if (index === 4) return 'active';
      return 'pending';
    }
    if (status === 'fixing' || status === 'validating') {
      if (index < 5) return 'completed';
      if (index === 5) return 'active';
      return 'pending';
    }
    return 'completed';
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="live-tracker-panel">
      <div className="tracker-header">
        <div className="tracker-title-col">
          <div className="tracker-badge">
            <span className="pulse-indicator" />
            <span>AI Agents Actively Analyzing</span>
            <span style={{ marginLeft: '0.5rem', padding: '0.15rem 0.5rem', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>⚡ Multi-Threaded</span>
          </div>
          <h3 className="tracker-repo-name">
            {repo} <span className="pr-highlight">#{prNumber}</span>
          </h3>
          <p className="tracker-desc">
            LangGraph multi-agent execution pipeline evaluating code modifications, security alerts, and generating remediation diffs.
          </p>
        </div>

        <div className="tracker-timer-card">
          <span className="timer-label">ELAPSED TIME</span>
          <span className="timer-value">{formatSeconds(elapsed)}</span>
          <span className="timer-sub">{runId ? 'Polling real backend' : 'Connecting orchestrator...'}</span>
        </div>
      </div>

      {/* 7-Stage Pipeline Visualizer */}
      <div className="stages-timeline">
        {STAGES.map((st, idx) => {
          const state = getStageState(idx);
          return (
            <div key={st.id} className={`timeline-stage-card ${state}`}>
              <div className="stage-icon-wrap">
                {state === 'completed' ? (
                  <span className="stage-check">✓</span>
                ) : state === 'active' ? (
                  <div className="stage-spinner" />
                ) : (
                  <span className="stage-icon-dim">{st.icon}</span>
                )}
              </div>

              <div className="stage-body">
                <span className="stage-agent-label">{st.agent}</span>
                <h4 className="stage-name">{st.title}</h4>
                <p className="stage-desc">{st.desc}</p>
              </div>

              <div className="stage-status-indicator">
                {state === 'completed' && <span className="badge-done">Done</span>}
                {state === 'active' && <span className="badge-active">Running</span>}
                {state === 'pending' && <span className="badge-wait">Queued</span>}
              </div>
            </div>
          );
        })}
      </div>

      {pollError && (
        <div style={{ marginTop: '1.25rem', padding: '1rem 1.25rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <div>
            <div style={{ color: '#ef4444', fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.25rem' }}>⚠️ Analysis Error</div>
            <div style={{ color: '#fca5a5', fontSize: '0.825rem' }}>
              {pollError}
            </div>
          </div>
          <button
            onClick={handleRetryRun}
            disabled={isRetrying}
            style={{ padding: '0.5rem 1rem', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
          >
            {isRetrying ? 'Triggering...' : 'Re-run Analysis'}
          </button>
        </div>
      )}

      {currentRun?.status === 'failed' && (
        <div style={{ marginTop: '1.25rem', padding: '1rem 1.25rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <div>
            <div style={{ color: '#ef4444', fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.25rem' }}>⚠️ Analysis Encountered An Issue</div>
            <div style={{ color: '#fca5a5', fontSize: '0.825rem' }}>
              {currentRun.notes && currentRun.notes.length > 0 ? currentRun.notes[0] : 'The background workflow encountered an error. Click retry to run fresh.'}
            </div>
          </div>
          <button
            onClick={() => window.location.reload()}
            style={{ padding: '0.5rem 1rem', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
          >
            Retry Analysis
          </button>
        </div>
      )}

      {elapsed > 60 && !isDone && currentRun?.status !== 'failed' && (
        <div style={{ marginTop: '1.25rem', padding: '0.85rem 1.25rem', background: 'rgba(234, 179, 8, 0.08)', border: '1px solid rgba(234, 179, 8, 0.3)', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <div style={{ fontSize: '0.875rem', color: '#facc15', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>⏱️</span>
            <span>Analysis running on Azure OpenAI GPT-4.1. If this run was previously blocked, you can refresh or re-analyze.</span>
          </div>
          <button
            onClick={() => window.location.reload()}
            style={{ padding: '0.45rem 1rem', fontSize: '0.8rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap' }}
          >
            Refresh Status
          </button>
        </div>
      )}
    </div>
  );
};
