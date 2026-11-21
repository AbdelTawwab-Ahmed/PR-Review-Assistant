import React, { useState, useMemo } from 'react';
import type { Finding, Severity } from '../types/run';

interface FindingsListProps {
  findings?: Finding[];
  count?: number;
}

export const FindingsList: React.FC<FindingsListProps> = ({ findings = [], count }) => {
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const totalCount = count !== undefined ? count : findings.length;

  const counts = useMemo(() => {
    return {
      all: totalCount,
      critical: findings.filter((f) => f.severity.toLowerCase() === 'critical').length,
      high: findings.filter((f) => f.severity.toLowerCase() === 'high').length,
      medium: findings.filter((f) => f.severity.toLowerCase() === 'medium').length,
      low: findings.filter((f) => f.severity.toLowerCase() === 'low').length,
    };
  }, [findings, totalCount]);

  const filtered = useMemo(() => {
    return findings.filter((f) => {
      const matchSeverity =
        filterSeverity === 'ALL' || f.severity.toLowerCase() === filterSeverity.toLowerCase();
      const matchSearch =
        !searchQuery.trim() ||
        f.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (f.file_path && f.file_path.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchSeverity && matchSearch;
    });
  }, [findings, filterSeverity, searchQuery]);

  const getSeverityBadge = (sev: Severity | string) => {
    const s = sev.toLowerCase();
    let badgeClass = 'badge-medium';
    if (s === 'critical') badgeClass = 'badge-critical';
    if (s === 'high') badgeClass = 'badge-high';
    if (s === 'low') badgeClass = 'badge-low';

    return (
      <span className={`finding-severity-pill ${badgeClass}`}>
        <span className="dot" />
        {sev.toUpperCase()}
      </span>
    );
  };

  const getCategoryIcon = (cat: string) => {
    const c = cat.toLowerCase();
    if (c.includes('security')) return '🛡️';
    if (c.includes('bug') || c.includes('error')) return '🐛';
    if (c.includes('perf')) return '⚡';
    return '📐';
  };

  return (
    <div className="findings-container-elevated">
      {/* Top Filter Bar */}
      <div className="findings-filter-bar">
        <div className="severity-filter-chips">
          {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((lvl) => {
            const countForLvl =
              lvl === 'ALL'
                ? counts.all
                : counts[lvl.toLowerCase() as keyof typeof counts];

            return (
              <button
                key={lvl}
                onClick={() => setFilterSeverity(lvl)}
                className={`sev-filter-chip ${filterSeverity === lvl ? 'active' : ''} sev-${lvl.toLowerCase()}`}
              >
                {lvl}
                <span className="chip-bubble">{countForLvl}</span>
              </button>
            );
          })}
        </div>

        <div className="findings-search-box">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            placeholder="Search findings by rule, description, file..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="findings-search-input"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} className="btn-clear-search">
              &times;
            </button>
          )}
        </div>
      </div>

      {/* Findings List or Empty State */}
      {filtered.length === 0 ? (
        <div className="findings-empty-card">
          <div className="empty-check-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h4 className="empty-check-title">No Findings Match Filter</h4>
          <p className="empty-check-desc">
            {findings.length === 0
              ? 'Static analysis tools (Ruff, Bandit, Semgrep) completed with zero reported issues.'
              : 'Try clearing the search query or selecting a different severity tier.'}
          </p>
        </div>
      ) : (
        <div className="findings-card-grid">
          {filtered.map((item, idx) => (
            <div key={idx} className={`finding-item-card severity-${item.severity.toLowerCase()}`}>
              <div className="finding-header-row">
                <div className="badges-group">
                  {getSeverityBadge(item.severity)}
                  <span className="category-tag">
                    <span className="cat-icon">{getCategoryIcon(item.category)}</span>
                    {item.category}
                  </span>
                  {item.source && <span className="source-tool-tag">{item.source}</span>}
                </div>

                {item.file_path && (
                  <div className="file-anchor-tag">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <code>{item.file_path}</code>
                    {item.line_start && <span className="line-highlight">:{item.line_start}</span>}
                  </div>
                )}
              </div>

              <h4 className="finding-item-title">{item.title}</h4>
              <p className="finding-item-desc">{item.description}</p>

              {item.suggestion && (
                <div className="finding-recommendation-box">
                  <div className="rec-header">
                    <span className="rec-icon">💡</span>
                    <span className="rec-title">Remediation Advice</span>
                  </div>
                  <p className="rec-text">{item.suggestion}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
