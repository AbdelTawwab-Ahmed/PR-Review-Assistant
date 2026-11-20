import React from 'react';
import type { RunStatus } from '../types/run';

interface StatusBadgeProps {
  status: RunStatus;
  size?: 'sm' | 'md' | 'lg';
}

const statusConfig: Record<RunStatus, { label: string; className: string; pulse?: boolean }> = {
  pending: { label: 'Pending', className: 'status-pending' },
  analyzing: { label: 'Analyzing Code', className: 'status-running', pulse: true },
  planning: { label: 'Planning Fixes', className: 'status-running', pulse: true },
  fixing: { label: 'Applying Fixes', className: 'status-running', pulse: true },
  validating: { label: 'Validating Tests', className: 'status-running', pulse: true },
  awaiting_approval: { label: 'Awaiting Approval', className: 'status-awaiting', pulse: true },
  updating_pr: { label: 'Updating PR', className: 'status-running', pulse: true },
  ready_to_merge: { label: 'Ready to Merge', className: 'status-success' },
  rejected: { label: 'Rejected', className: 'status-rejected' },
  failed: { label: 'Failed', className: 'status-failed' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const config = statusConfig[status] || { label: status, className: 'status-pending' };

  return (
    <span className={`status-badge ${config.className} size-${size}`}>
      {config.pulse && <span className="pulse-dot" />}
      <span className="status-text">{config.label}</span>
    </span>
  );
};
