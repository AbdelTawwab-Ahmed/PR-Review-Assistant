import React, { useState } from 'react';
import type { FileChange } from '../types/run';

interface DiffViewerProps {
  changes: FileChange[];
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

  const origLines = activeFile.original_content ? activeFile.original_content.split('\n') : [];
  const updatedLines = activeFile.updated_content ? activeFile.updated_content.split('\n') : [];

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
          <span className="diff-stat-chip added">+{updatedLines.length}</span>
          <span className="diff-stat-chip deleted">-{origLines.length}</span>
        </div>
        <span className="ai-verified-tag">✨ AI Remediated</span>
      </div>

      {/* Code Diff Display */}
      {viewMode === 'split' ? (
        <div className="split-diff-container">
          <div className="diff-pane original-pane">
            <div className="diff-pane-header">Original Base Code</div>
            <div className="code-scroll-pane">
              {origLines.map((line, idx) => {
                const isDifferent = updatedLines[idx] !== line;
                return (
                  <div key={idx} className={`code-row ${isDifferent ? 'row-removed' : ''}`}>
                    <span className="row-num">{idx + 1}</span>
                    <span className="row-sign">{isDifferent ? '-' : ' '}</span>
                    <pre className="row-text">{line || ' '}</pre>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="diff-pane updated-pane">
            <div className="diff-pane-header">Proposed AI Solution</div>
            <div className="code-scroll-pane">
              {updatedLines.map((line, idx) => {
                const isDifferent = origLines[idx] !== line;
                return (
                  <div key={idx} className={`code-row ${isDifferent ? 'row-added' : ''}`}>
                    <span className="row-num">{idx + 1}</span>
                    <span className="row-sign">{isDifferent ? '+' : ' '}</span>
                    <pre className="row-text">{line || ' '}</pre>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="unified-diff-container">
          <div className="code-scroll-pane">
            {updatedLines.map((line, idx) => {
              const origLine = origLines[idx];
              const isAdded = origLine !== line;
              return (
                <div key={idx} className={`code-row ${isAdded ? 'row-added' : ''}`}>
                  <span className="row-num">{idx + 1}</span>
                  <span className="row-sign">{isAdded ? '+' : ' '}</span>
                  <pre className="row-text">{line || ' '}</pre>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
