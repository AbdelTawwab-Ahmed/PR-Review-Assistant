import React, { useState, useEffect } from 'react';
import { getRun } from '../api/runs';
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

  // Timer
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Poll backend run status
  useEffect(() => {
    let isCancelled = false;

    const poll = async () => {
      try {
        const detail = await getRun(runId);
        if (isCancelled) return;
        setCurrentRun(detail);

        if (detail.status === 'awaiting_approval' || detail.status === 'ready_to_merge' || detail.status === 'rejected' || detail.status === 'failed') {
          setIsDone(true);
          onAnalysisCompleted(detail);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [runId, onAnalysisCompleted]);

  // Determine stage progress based on actual backend status
  const getStageState = (index: number): 'completed' | 'active' | 'pending' => {
    if (isDone) return 'completed';

    const status = currentRun?.status || 'analyzing';

    if (status === 'pending') {
      return index === 0 ? 'active' : 'pending';
    }
    if (status === 'analyzing') {
      if (index < 2) return 'completed';
      if (index === 2 || index === 3) return 'active';
      return 'pending';
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
          <span className="timer-sub">Polling real backend</span>
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
    </div>
  );
};
