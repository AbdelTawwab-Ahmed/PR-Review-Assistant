import React from 'react';
import type { RunStatus } from '../types/run';

interface AgentPipelineProps {
  status: RunStatus;
}

interface Step {
  id: string;
  name: string;
  description: string;
  icon: string;
}

const PIPELINE_STEPS: Step[] = [
  { id: 'ingest', name: 'Repo Ingestion', description: 'Project structure & files indexed', icon: '📥' },
  { id: 'analysis', name: 'Deep Analysis', description: 'Bugs, security, perf & error handling', icon: '🔍' },
  { id: 'hitl1', name: 'Gate 1: Authorization', description: 'Human approval for remediation', icon: '🛡️' },
  { id: 'remediation', name: 'Remediation Agents', description: 'Targeted code patches formulated', icon: '🤖' },
  { id: 'validation', name: 'Sandbox Validation', description: 'Pytest & linting regression checks', icon: '🧪' },
  { id: 'hitl2', name: 'Gate 2: Diff Review', description: 'Human review of verified fixes', icon: '⚖️' },
  { id: 'published', name: 'PR Published', description: 'Verified branch & pull request created', icon: '🚀' },
];

function getStepState(
  stepIndex: number,
  currentStatus: RunStatus
): 'completed' | 'current' | 'pending' | 'failed' | 'rejected' {
  if (currentStatus === 'failed') {
    return 'failed';
  }
  if (currentStatus === 'rejected') {
    // Stage 1 or Stage 2 rejection
    if (stepIndex === 2 || stepIndex === 5) return 'rejected';
  }

  const statusToIndex: Record<RunStatus, number> = {
    pending: 0,
    analyzing: 1,
    awaiting_plan_approval: 2,
    planning: 3,
    fixing: 3,
    validating: 4,
    awaiting_approval: 5,
    updating_pr: 6,
    ready_to_merge: 6,
    rejected: 2,
    failed: 1,
  };

  const currentIndex = statusToIndex[currentStatus] ?? 0;

  if (currentStatus === 'ready_to_merge' && stepIndex <= 6) {
    return 'completed';
  }

  if (stepIndex < currentIndex) {
    return 'completed';
  }
  if (stepIndex === currentIndex) {
    return 'current';
  }
  return 'pending';
}

export const AgentPipeline: React.FC<AgentPipelineProps> = ({ status }) => {
  return (
    <div className="agent-pipeline-card">
      <div className="pipeline-header">
        <div className="pipeline-title-wrap">
          <div className="pipeline-agent-badge">
            <span className="sparkle">✨</span> LangGraph Autonomous Agent Pipeline
          </div>
          <span className="pipeline-status-text">
            Status: <strong>{status.replace(/_/g, ' ').toUpperCase()}</strong>
          </span>
        </div>
      </div>

      <div className="pipeline-stepper">
        {PIPELINE_STEPS.map((step, idx) => {
          const state = getStepState(idx, status);
          return (
            <div key={step.id} className={`pipeline-step-item state-${state}`}>
              <div className="step-connector" />
              <div className="step-circle">
                {state === 'completed' ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : state === 'current' ? (
                  <span className="step-pulse" />
                ) : (
                  <span className="step-icon">{step.icon}</span>
                )}
              </div>
              <div className="step-info">
                <span className="step-name">{step.name}</span>
                <span className="step-desc">{step.description}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
