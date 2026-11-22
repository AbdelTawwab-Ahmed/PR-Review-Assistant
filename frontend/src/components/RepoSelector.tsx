import React, { useState, useEffect } from 'react';
import { getUserRepos, getRepoDetails, type UserRepoItem, type RepoDetailsResponse } from '../api/repos';

interface RepoSelectorProps {
  onAnalyze: (repo: string, prNumber?: number) => void;
  isAnalyzing: boolean;
}

export const RepoSelector: React.FC<RepoSelectorProps> = ({ onAnalyze, isAnalyzing }) => {
  const [inputVal, setInputVal] = useState('');
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [selectedPr, setSelectedPr] = useState<number | undefined>(undefined);

  const [userRepos, setUserRepos] = useState<UserRepoItem[]>([]);
  const [repoDetails, setRepoDetails] = useState<RepoDetailsResponse | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Load connected user repositories on mount
  useEffect(() => {
    getUserRepos()
      .then((repos) => {
        if (repos && repos.length > 0) {
          setUserRepos(repos);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch repository details whenever selectedRepo changes
  useEffect(() => {
    if (!selectedRepo || !selectedRepo.includes('/')) return;

    let isMounted = true;
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
      .catch((err) => {
        if (!isMounted) return;
        setValidationError(err?.message || 'Could not fetch repository information.');
        setRepoDetails(null);
      })
      .finally(() => {
        if (isMounted) setIsLoadingDetails(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedRepo]);

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
      setValidationError(null);
    }
  };

  const handleSelectConnectedRepo = (repoName: string) => {
    setInputVal(`https://github.com/${repoName}`);
    setSelectedRepo(repoName);
    setValidationError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseRepoString(inputVal);
    if (!parsed) {
      setValidationError('Please enter a valid GitHub repository URL.');
      return;
    }
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
            Repository Selection
          </div>
          <h2 className="section-title">Connect & Analyze GitHub Repository</h2>
          <p className="section-desc">
            Enter any public or private GitHub repository to trigger the LangGraph AI multi-agent code & security audit.
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
            placeholder="Paste GitHub Repository URL (e.g. https://github.com/owner/repo or owner/repo)"
            value={inputVal}
            onChange={handleInputChange}
            disabled={isAnalyzing}
          />
          {isLoadingDetails && <div className="input-spinner" />}
        </div>

        <button
          type="submit"
          className="btn btn-primary analyze-action-btn"
          disabled={isAnalyzing || !selectedRepo || !!validationError}
        >
          {isAnalyzing ? (
            <>
              <div className="spinner small" />
              <span>Analyzing Codebase...</span>
            </>
          ) : (
            <>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              <span>Analyze Repository</span>
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

      {/* Quick Select Connected Repositories */}
      {userRepos.length > 0 && (
        <div className="quick-repos-bar">
          <span className="quick-repos-label">Connected Repositories:</span>
          <div className="quick-repos-chips">
            {userRepos.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`quick-repo-chip ${selectedRepo === r.full_name ? 'selected' : ''}`}
                onClick={() => handleSelectConnectedRepo(r.full_name)}
              >
                <span className="chip-repo-icon">📁</span>
                <span className="chip-repo-text">{r.name}</span>
                {r.language && <span className="chip-lang-dot">{r.language}</span>}
              </button>
            ))}
          </div>
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
            <div className="no-open-prs-note">
              <span>ℹ️ No open pull requests found. Analysis will examine recent changes on the default branch <code>{repoDetails.repo.default_branch}</code>.</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
