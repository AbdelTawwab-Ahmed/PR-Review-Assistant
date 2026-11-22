import React, { useState } from 'react';
import type { FileChange } from '../types/run';

interface DiffViewerProps {
  changes: FileChange[];
}

interface DiffRow {
  type: 'equal' | 'add' | 'del';
  text: string;
  oldNum?: number;
  newNum?: number;
}

function computeLcsDiff(origLines: string[], newLines: string[]): DiffRow[] {
  const n = Math.min(origLines.length, 600);
  const m = Math.min(newLines.length, 600);
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < m; j++) {
      if (origLines[i] === newLines[j]) {
        dp[i + 1][j + 1] = dp[i][j] + 1;
      } else {
        dp[i + 1][j + 1] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const result: DiffRow[] = [];
  let i = n;
  let j = m;

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && origLines[i - 1] === newLines[j - 1]) {
      result.unshift({ type: 'equal', text: origLines[i - 1], oldNum: i, newNum: j });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'add', text: newLines[j - 1], newNum: j });
      j--;
    } else if (i > 0) {
      result.unshift({ type: 'del', text: origLines[i - 1], oldNum: i });
      i--;
    }
  }
  return result;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ changes }) => {
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  const [viewMode, setViewMode] = useState<'split' | 'unified'>('split');

  if (!changes || changes.length === 0) {
    return (
      <div className="diff-empty-state">
        <div className="diff-empty-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <polyline points="16 18 22 12 16 6" />
            <polyline points="8 6 2 12 8 18" />
          </svg>
        </div>
        <h4 className="diff-empty-title">No Code Modifications Proposed</h4>
        <p className="diff-empty-desc">
          The code either passed all automated quality criteria or fixes did not modify file content.
        </p>
      </div>
    );
  }

  const activeFile = changes[activeFileIndex] || changes[0];

  const origLines = (activeFile.original_content || '').split('\n');
  const updatedLines = (activeFile.updated_content || '').split('\n');
  const diffRows = computeLcsDiff(origLines, updatedLines);

  const additions = diffRows.filter((r) => r.type === 'add').length;
  const deletions = diffRows.filter((r) => r.type === 'del').length;

  return (
    <div className="diff-viewer-elevated">
      {/* File Navigation Tabs */}
      <div className="diff-toolbar">
        <div className="diff-file-tabs">
          {changes.map((file, idx) => (
            <button
              key={file.path}
              onClick={() => setActiveFileIndex(idx)}
              className={`file-tab-btn ${idx === activeFileIndex ? 'active' : ''}`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <span className="file-tab-name">{file.path.split('/').pop()}</span>
              <span className="file-tab-path-dim">{file.path}</span>
            </button>
          ))}
        </div>

        <div className="diff-view-toggle">
          <button
            className={`toggle-btn ${viewMode === 'split' ? 'active' : ''}`}
            onClick={() => setViewMode('split')}
            title="Split side-by-side view"
          >
            Split
          </button>
          <button
            className={`toggle-btn ${viewMode === 'unified' ? 'active' : ''}`}
            onClick={() => setViewMode('unified')}
            title="Unified linear view"
          >
            Unified
          </button>
        </div>
      </div>

      {/* File Header Bar */}
      <div className="file-header-bar">
        <div className="file-name-meta">
          <span className="file-icon">📄</span>
          <code className="file-full-path">{activeFile.path}</code>
          <span className="diff-stat-chip added">+{additions}</span>
          <span className="diff-stat-chip deleted">-{deletions}</span>
        </div>
        <span className="ai-verified-tag">✨ AI Remediated</span>
      </div>

      {/* Code Diff Display */}
      {viewMode === 'split' ? (
        <div className="split-diff-container">
          <div className="diff-pane original-pane">
            <div className="diff-pane-header">Original Base Code</div>
            <div className="code-scroll-pane">
              {diffRows.map((row, idx) => {
                if (row.type === 'add') return <div key={idx} className="code-row row-empty">&nbsp;</div>;
                return (
                  <div key={idx} className={`code-row ${row.type === 'del' ? 'row-removed' : ''}`}>
                    <span className="row-num">{row.oldNum || ' '}</span>
                    <span className="row-sign">{row.type === 'del' ? '-' : ' '}</span>
                    <pre className="row-text">{row.text || ' '}</pre>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="diff-pane updated-pane">
            <div className="diff-pane-header">Remediated Code Solution</div>
            <div className="code-scroll-pane">
              {diffRows.map((row, idx) => {
                if (row.type === 'del') return <div key={idx} className="code-row row-empty">&nbsp;</div>;
                return (
                  <div key={idx} className={`code-row ${row.type === 'add' ? 'row-added' : ''}`}>
                    <span className="row-num">{row.newNum || ' '}</span>
                    <span className="row-sign">{row.type === 'add' ? '+' : ' '}</span>
                    <pre className="row-text">{row.text || ' '}</pre>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="unified-diff-container">
          <div className="code-scroll-pane">
            {diffRows.map((row, idx) => {
              const rowClass = row.type === 'add' ? 'row-added' : row.type === 'del' ? 'row-removed' : '';
              const sign = row.type === 'add' ? '+' : row.type === 'del' ? '-' : ' ';
              return (
                <div key={idx} className={`code-row ${rowClass}`}>
                  <span className="row-num">{row.oldNum || row.newNum || ' '}</span>
                  <span className="row-sign">{sign}</span>
                  <pre className="row-text">{row.text || ' '}</pre>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
