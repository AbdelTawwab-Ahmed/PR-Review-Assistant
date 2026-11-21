import React from 'react';
import type { RiskReport } from '../types/run';

interface RiskGaugeProps {
  risk: RiskReport | null | undefined;
}

export const RiskGauge: React.FC<RiskGaugeProps> = ({ risk }) => {
  if (!risk) {
    return (
      <div className="risk-card-elevated empty">
        <div className="risk-empty-icon">⚖️</div>
        <h4 className="risk-empty-title">Risk Report Pending</h4>
        <p className="risk-empty-desc">Risk scoring will be calculated after static analysis completes.</p>
      </div>
    );
  }

  const score = Math.min(100, Math.max(0, risk.score));

  const getScoreTheme = (val: number) => {
    if (val < 30) {
      return {
        color: '#10B981',
        bg: 'rgba(16, 185, 129, 0.12)',
        label: 'Low Risk',
        desc: 'Changes are localized with minimal blast radius. Safe to merge once tests pass.',
      };
    }
    if (val < 65) {
      return {
        color: '#F59E0B',
        bg: 'rgba(245, 158, 11, 0.12)',
        label: 'Medium Risk',
        desc: 'Moderate architectural impact or security findings detected. Automated fixes applied.',
      };
    }
    return {
      color: '#EF4444',
      bg: 'rgba(239, 68, 68, 0.12)',
      label: 'High Risk',
      desc: 'Critical security alerts, broad file changes, or test regressions. Review recommended.',
    };
  };

  const theme = getScoreTheme(score);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="risk-card-elevated">
      <div className="risk-header-row">
        <div>
          <span className="risk-sub">Autonomous Blast Radius Evaluation</span>
          <h3 className="risk-main-title">Cumulative Pull Request Risk</h3>
        </div>
        <div className="risk-pill-badge" style={{ color: theme.color, backgroundColor: theme.bg }}>
          <span className="risk-pulse-dot" style={{ backgroundColor: theme.color }} />
          {risk.level.toUpperCase()} LEVEL
        </div>
      </div>

      <div className="risk-dashboard-body">
        {/* Left: Radial Gauge */}
        <div className="radial-gauge-col">
          <div className="gauge-svg-wrap">
            <svg width="160" height="160" viewBox="0 0 140 140" className="gauge-svg">
              <defs>
                <linearGradient id="riskGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor={theme.color} stopOpacity="0.8" />
                  <stop offset="100%" stopColor={theme.color} stopOpacity="1" />
                </linearGradient>
              </defs>
              <circle
                cx="70"
                cy="70"
                r={radius}
                fill="transparent"
                stroke="#1F2937"
                strokeWidth="10"
              />
              <circle
                cx="70"
                cy="70"
                r={radius}
                fill="transparent"
                stroke="url(#riskGradient)"
                strokeWidth="10"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                transform="rotate(-90 70 70)"
                style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
              />
              <text x="70" y="66" textAnchor="middle" className="gauge-score-value">
                {score}
              </text>
              <text x="70" y="86" textAnchor="middle" className="gauge-score-label">
                OUT OF 100
              </text>
            </svg>
          </div>

          <div className="risk-summary-text">
            <strong className="theme-label" style={{ color: theme.color }}>{theme.label}</strong>
            <p className="theme-desc">{theme.desc}</p>
          </div>
        </div>

        {/* Right: Factors Breakdown */}
        <div className="factors-breakdown-col">
          <div className="factors-header">
            <h4 className="factors-headline">Contributing Factors ({risk.factors.length})</h4>
            <span className="factors-info">Points added per detection</span>
          </div>

          {risk.factors.length === 0 ? (
            <div className="no-factors-box">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
              <span>No risk penalty points accrued. Clean execution.</span>
            </div>
          ) : (
            <div className="factor-cards-list">
              {risk.factors.map((factor, idx) => (
                <div key={idx} className="factor-item-card">
                  <div className="factor-points-badge">+{factor.points}</div>
                  <div className="factor-content">
                    <span className="factor-name-text">{factor.name}</span>
                    <span className="factor-reason-text">{factor.reason}</span>
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
