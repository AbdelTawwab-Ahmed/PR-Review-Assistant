import React from 'react';
import type { ReviewRunItem } from '../types/run';

interface StatsOverviewProps {
  runs: ReviewRunItem[];
}

export const StatsOverview: React.FC<StatsOverviewProps> = ({ runs }) => {
  const totalRuns = runs.length;
  const awaitingApproval = runs.filter((r) => r.status === 'awaiting_approval').length;
  const readyToMerge = runs.filter((r) => r.status === 'ready_to_merge' || r.status === 'updating_pr').length;
  const activeRuns = runs.filter((r) =>
    ['analyzing', 'planning', 'fixing', 'validating'].includes(r.status)
  ).length;

  const validScores = runs
    .map((r) => r.risk?.score)
    .filter((s): s is number => typeof s === 'number');
  const avgRisk = validScores.length
    ? Math.round(validScores.reduce((a, b) => a + b, 0) / validScores.length)
    : 0;

  return (
    <div className="stats-grid">
      <div className="stat-card">
        <div className="stat-header">
          <span className="stat-label">Total Reviews</span>
          <div className="stat-icon-wrapper icon-blue">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="18" cy="18" r="3" />
              <circle cx="6" cy="6" r="3" />
              <path d="M13 6h3a2 2 0 0 1 2 2v7" />
              <line x1="6" y1="9" x2="6" y2="21" />
            </svg>
          </div>
        </div>
        <div className="stat-value-row">
          <span className="stat-value">{totalRuns}</span>
          {activeRuns > 0 && (
            <span className="stat-pill pill-blue">
              <span className="pulse-dot" />
              {activeRuns} running
            </span>
          )}
        </div>
        <span className="stat-subtext">Autonomous PR review cycles</span>
      </div>

      <div className={`stat-card ${awaitingApproval > 0 ? 'stat-card-highlight' : ''}`}>
        <div className="stat-header">
          <span className="stat-label">Action Required</span>
          <div className="stat-icon-wrapper icon-amber">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
        </div>
        <div className="stat-value-row">
          <span className="stat-value text-amber">{awaitingApproval}</span>
          {awaitingApproval > 0 && (
            <span className="stat-pill pill-amber">
              <span className="pulse-dot" />
              Human Gate
            </span>
          )}
        </div>
        <span className="stat-subtext">Awaiting human authorization</span>
      </div>

      <div className="stat-card">
        <div className="stat-header">
          <span className="stat-label">Verified & Ready</span>
          <div className="stat-icon-wrapper icon-emerald">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
        </div>
        <div className="stat-value-row">
          <span className="stat-value text-emerald">{readyToMerge}</span>
          <span className="stat-pill pill-emerald">Resolved</span>
        </div>
        <span className="stat-subtext">Fixes generated & passed checks</span>
      </div>

      <div className="stat-card">
        <div className="stat-header">
          <span className="stat-label">Avg Risk Score</span>
          <div className="stat-icon-wrapper icon-purple">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
          </div>
        </div>
        <div className="stat-value-row">
          <span className="stat-value">{avgRisk}<span className="stat-unit">/100</span></span>
          <span className={`stat-pill ${avgRisk > 60 ? 'pill-red' : avgRisk > 30 ? 'pill-amber' : 'pill-emerald'}`}>
            {avgRisk > 60 ? 'High' : avgRisk > 30 ? 'Medium' : 'Low'}
          </span>
        </div>
        <span className="stat-subtext">Aggregated across active callsets</span>
      </div>
    </div>
  );
};
