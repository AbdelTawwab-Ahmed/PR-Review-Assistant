import React from 'react';
import type { RiskReport } from '../types/run';

interface RiskGaugeProps {
  risk: RiskReport | null | undefined;
}

export const RiskGauge: React.FC<RiskGaugeProps> = ({ risk }) => {
  if (!risk) {
    return (
      <div className="risk-card empty">
        <p className="empty-text">No risk report calculated yet.</p>
      </div>
    );
  }

  const score = Math.min(100, Math.max(0, risk.score));
  const getScoreColor = (val: number) => {
    if (val < 30) return '#10B981'; // emerald
    if (val < 60) return '#F59E0B'; // amber
    if (val < 85) return '#F97316'; // orange
    return '#EF4444'; // red
  };

  const strokeColor = getScoreColor(score);
  const circumference = 2 * Math.PI * 40;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="risk-card">
      <div className="risk-header">
        <h3 className="section-title">Risk Assessment</h3>
        <span className={`risk-level-tag level-${risk.level.toLowerCase()}`}>
          {risk.level.toUpperCase()} RISK
        </span>
      </div>

      <div className="risk-body">
        <div className="gauge-container">
          <svg className="gauge-svg" width="120" height="120" viewBox="0 0 100 100">
            <circle
              className="gauge-bg"
              cx="50"
              cy="50"
              r="40"
              fill="transparent"
              stroke="#1F2937"
              strokeWidth="8"
            />
            <circle
              className="gauge-progress"
              cx="50"
              cy="50"
              r="40"
              fill="transparent"
              stroke={strokeColor}
              strokeWidth="8"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              transform="rotate(-90 50 50)"
            />
            <text
              x="50"
              y="48"
              textAnchor="middle"
              className="gauge-value"
              fill="#F9FAFB"
            >
              {score}
            </text>
            <text
              x="50"
              y="64"
              textAnchor="middle"
              className="gauge-label"
              fill="#9CA3AF"
            >
              / 100
            </text>
          </svg>
        </div>

        <div className="factors-list">
          <h4 className="factors-title">Contributing Risk Factors ({risk.factors.length})</h4>
          {risk.factors.length === 0 ? (
            <p className="no-factors">No negative risk factors identified.</p>
          ) : (
            <div className="factor-items">
              {risk.factors.map((factor, idx) => (
                <div key={idx} className="factor-row">
                  <div className="factor-badge">+{factor.points}</div>
                  <div className="factor-details">
                    <span className="factor-name">{factor.name}</span>
                    <span className="factor-reason">{factor.reason}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
