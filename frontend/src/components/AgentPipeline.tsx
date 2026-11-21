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
  { id: 'ingest', name: 'PR Ingestion', description: 'Diffs & commits fetched', icon: '📥' },
  { id: 'analysis', name: 'Static Analysis', description: 'Ruff, Bandit & Semgrep', icon: '🔍' },
  { id: 'risk', name: 'Risk Scoring', description: 'Blast radius evaluation', icon: '⚖️' },
  { id: 'fix', name: 'Agentic Fixer', description: 'Multi-agent LLM reasoning', icon: '🤖' },
  { id: 'validate', name: 'Validation', description: 'Pytest suite execution', icon: '🧪' },
  { id: 'hitl', name: 'Human Gate', description: 'HITL Authorization', icon: '🛡️' },
  { id: 'merge', name: 'PR Published', description: 'Fix branch committed', icon: '🚀' },
];

function getStepState(
  stepIndex: number,
  currentStatus: RunStatus
): 'completed' | 'current' | 'pending' | 'failed' | 'rejected' {
  if (currentStatus === 'failed') {
    return 'failed';
  }
  if (currentStatus === 'rejected' && stepIndex === 5) {
    return 'rejected';
  }

  const statusToIndex: Record<RunStatus, number> = {
    pending: 0,
    analyzing: 1,
    planning: 2,
    fixing: 3,
    validating: 4,
    awaiting_approval: 5,
    updating_pr: 6,
    ready_to_merge: 6,
    rejected: 5,
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
