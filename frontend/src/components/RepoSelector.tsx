import React, { useState, useEffect } from 'react';
import { getRepoDetails } from '../api/repos';
import { useDashboardState } from '../context/dashboardState';

interface RepoSelectorProps {
  onAnalyze: (repo: string, prNumber?: number) => void;
  isAnalyzing: boolean;
}

export const RepoSelector: React.FC<RepoSelectorProps> = ({ onAnalyze, isAnalyzing }) => {
  const {
    inputVal,
    setInputVal,
    selectedRepo,
    setSelectedRepo,
    selectedPr,
    setSelectedPr,
    repoDetails,
    setRepoDetails,
  } = useDashboardState();

  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Fetch repository details whenever selectedRepo changes and isn't already loaded
  useEffect(() => {
    if (!selectedRepo || !selectedRepo.includes('/')) return;
    if (repoDetails?.repo.full_name.toLowerCase() === selectedRepo.toLowerCase()) {
      return;
    }

    let isMounted = true;
    const timer = setTimeout(() => {
      if (!isMounted) return;
      setIsLoadingDetails(true);
      setValidationError(null);

      getRepoDetails(selectedRepo)
        .then((data) => {
          if (!isMounted) return;
          setRepoDetails(data);
          if (data.url_pr_number) {
            setSelectedPr(data.url_pr_number);
          } else if (data.open_prs && data.open_prs.length > 0) {
            setSelectedPr(data.open_prs[0].number);
          } else {
            setSelectedPr(undefined);
          }
        })
        .catch((err: unknown) => {
          if (!isMounted) return;
          const message = err instanceof Error ? err.message : 'Could not fetch repository information.';
          setValidationError(message);
          setRepoDetails(null);
        })
        .finally(() => {
          if (isMounted) setIsLoadingDetails(false);
        });
    }, 0);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [selectedRepo, repoDetails, setRepoDetails, setSelectedPr]);

  // Clean and parse repository string
  const parseRepoString = (raw: string): { repo: string; prNum?: number } | null => {
    const trimmed = raw.trim();
    if (!trimmed) return null;

    let clean = trimmed.replace(/^https?:\/\/github\.com\//i, '').replace(/\.git$/i, '');
    let prNum: number | undefined = undefined;

    if (clean.includes('/pull/')) {
      const parts = clean.split('/pull/');
      clean = parts[0];
      const parsedPr = parseInt(parts[1].split('/')[0], 10);
      if (!isNaN(parsedPr)) prNum = parsedPr;
    } else if (clean.includes('#')) {
      const parts = clean.split('#');
      clean = parts[0];
      const parsedPr = parseInt(parts[1], 10);
      if (!isNaN(parsedPr)) prNum = parsedPr;
    }

    const segments = clean.split('/').filter(Boolean);
    if (segments.length >= 2) {
      return { repo: `${segments[0]}/${segments[1]}`, prNum };
    }
    return null;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputVal(val);

    const parsed = parseRepoString(val);
    if (parsed) {
      setSelectedRepo(parsed.repo);
      if (parsed.prNum) setSelectedPr(parsed.prNum);
      setValidationError(null);
    } else if (val.trim()) {
      setValidationError('Please enter a valid GitHub repository (e.g. owner/repo or https://github.com/owner/repo)');
    } else {
      setSelectedRepo('');
      setSelectedPr(undefined);
      setRepoDetails(null);
      setValidationError(null);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseRepoString(inputVal);
    if (!parsed) {
      setValidationError('Please enter a valid GitHub repository (e.g. owner/repo or https://github.com/owner/repo)');
      return;
    }
    setValidationError(null);
    onAnalyze(parsed.repo, selectedPr || parsed.prNum);
  };

  return (
    <section className="repo-selection-card">
      <div className="section-header-row">
        <div className="section-title-wrap">
          <div className="section-pill">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
            Repository Analysis & Remediation
          </div>
          <h2 className="section-title">Automated Repository Analysis & Code Remediation</h2>
          <p className="section-desc">
            Enter any public or private GitHub repository URL to trigger the autonomous multi-agent analysis and two-stage Human-in-the-Loop remediation engine.
          </p>
        </div>
      </div>

      {/* Main Input Form */}
      <form onSubmit={handleSubmit} className="repo-form">
        <div className="repo-input-container">
          <div className="repo-icon-wrap">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
            </svg>
          </div>
          <input
            type="text"
            className="repo-text-input"
            placeholder="Enter GitHub Repository URL (e.g. https://github.com/owner/repo or owner/repo)"
            value={inputVal}
            onChange={handleInputChange}
            disabled={isAnalyzing}
          />
          {isLoadingDetails && <div className="input-spinner" />}
        </div>

        <button
          type="submit"
          className="btn btn-primary analyze-action-btn"
          disabled={isAnalyzing || !inputVal.trim()}
        >
          {isAnalyzing ? (
            <>
              <div className="spinner small" />
              <span>Analyzing Repository...</span>
            </>
          ) : (
            <>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              <span>Start Analysis Repo</span>
            </>
          )}
        </button>
      </form>

      {validationError && (
        <div className="repo-error-banner">
          <span className="error-icon">⚠️</span>
          <span>{validationError}</span>
        </div>
      )}

      {/* Selected Repository Card Preview */}
      {repoDetails && (
        <div className="selected-repo-preview">
          <div className="preview-top">
            <div className="preview-owner-badge">
              <img
                src={repoDetails.repo.owner.avatar_url || 'https://github.com/github.png'}
                alt={repoDetails.repo.owner.login}
                className="owner-avatar-img"
              />
              <div className="repo-meta-col">
                <div className="repo-name-heading">
                  <span className="repo-title-full">{repoDetails.repo.full_name}</span>
                  <span className="repo-badge-branch">Branch: {repoDetails.repo.default_branch}</span>
                  <span className="repo-badge-lang">{repoDetails.repo.language}</span>
                </div>
                <p className="repo-desc-text">{repoDetails.repo.description}</p>
              </div>
            </div>

            <div className="repo-metrics-group">
              <div className="metric-chip" title="GitHub Stars">
                <span>⭐</span>
                <span>{repoDetails.repo.stars} stars</span>
              </div>
              <div className="metric-chip" title="Forks">
                <span>🍴</span>
                <span>{repoDetails.repo.forks} forks</span>
              </div>
              <div className="metric-chip open-prs" title="Open Pull Requests">
                <span>🔀</span>
                <span>{repoDetails.open_prs.length} Open PRs</span>
              </div>
            </div>
          </div>

          {/* Pull Request Target Selection */}
          {repoDetails.open_prs.length > 0 ? (
            <div className="pr-target-selector">
              <span className="pr-target-label">Target Pull Request for Code Review:</span>
              <div className="pr-radio-list">
                {repoDetails.open_prs.map((pr) => (
                  <label
                    key={pr.number}
                    className={`pr-radio-item ${selectedPr === pr.number ? 'selected' : ''}`}
                  >
                    <input
                      type="radio"
                      name="selectedPr"
                      value={pr.number}
                      checked={selectedPr === pr.number}
                      onChange={() => setSelectedPr(pr.number)}
                    />
                    <div className="pr-item-content">
                      <span className="pr-item-number">#{pr.number}</span>
                      <span className="pr-item-title">{pr.title}</span>
                      <span className="pr-item-branch">{pr.head_branch} &rarr; {pr.base_branch}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <div className="no-open-prs-note" style={{ background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px', color: '#facc15', fontSize: '0.85rem' }}>
              <span>⚠️ No pull requests found on this repository. This assistant analyzes <strong>Pull Requests</strong>. Please open a PR or enter a repository that has PRs (e.g. <code>https://github.com/AbdelTawwab-Ahmed/PR-Review-Assistant/pull/19</code>).</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
