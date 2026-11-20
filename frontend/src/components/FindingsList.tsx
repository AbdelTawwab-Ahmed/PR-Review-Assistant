import React, { useState } from 'react';
import type { Finding, Severity } from '../types/run';

interface FindingsListProps {
  findings?: Finding[];
  count?: number;
}

export const FindingsList: React.FC<FindingsListProps> = ({ findings = [], count = 0 }) => {
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');

  const filtered = filterSeverity === 'ALL'
    ? findings
    : findings.filter((f) => f.severity.toLowerCase() === filterSeverity.toLowerCase());

  const getSeverityBadge = (sev: Severity | string) => {
    const s = sev.toLowerCase();
    let badgeClass = 'badge-medium';
    if (s === 'critical') badgeClass = 'badge-critical';
    if (s === 'high') badgeClass = 'badge-high';
    if (s === 'low') badgeClass = 'badge-low';

    return <span className={`finding-severity ${badgeClass}`}>{sev.toUpperCase()}</span>;
  };

  return (
    <div className="findings-section">
      <div className="findings-header">
        <div className="findings-title-group">
          <h3 className="section-title">Static Analysis & Review Findings</h3>
          <span className="findings-count-badge">{count || findings.length} detected</span>
        </div>

        <div className="findings-filter-group">
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setFilterSeverity(lvl)}
              className={`filter-btn ${filterSeverity === lvl ? 'active' : ''}`}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="findings-empty">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          <p>No findings matching the selected filter criteria.</p>
        </div>
      ) : (
        <div className="findings-grid">
          {filtered.map((item, idx) => (
            <div key={idx} className="finding-card">
              <div className="finding-card-top">
                {getSeverityBadge(item.severity)}
                <span className="finding-category">{item.category}</span>
                {item.file_path && (
                  <span className="finding-location">
                    <code>{item.file_path}</code>
                    {item.line_start && <span>:{item.line_start}</span>}
                  </span>
                )}
              </div>

              <h4 className="finding-title">{item.title}</h4>
              <p className="finding-desc">{item.description}</p>

              {item.suggestion && (
                <div className="finding-suggestion">
                  <span className="sugg-label">Recommendation:</span>
                  <p className="sugg-text">{item.suggestion}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
