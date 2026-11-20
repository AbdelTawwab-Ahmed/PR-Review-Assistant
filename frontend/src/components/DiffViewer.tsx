import React, { useState } from 'react';
import type { FileChange } from '../types/run';

interface DiffViewerProps {
  changes: FileChange[];
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ changes }) => {
  const [activeFileIndex, setActiveFileIndex] = useState(0);

  if (!changes || changes.length === 0) {
    return <div className="diff-empty">No file modifications proposed.</div>;
  }

  const activeFile = changes[activeFileIndex] || changes[0];

  const renderSimpleDiff = (orig: string, updated: string) => {
    const origLines = orig ? orig.split('\n') : [];
    const updatedLines = updated ? updated.split('\n') : [];

    // Simple diff display: compare line by line or display updated with indicators
    return (
      <div className="diff-code-container">
        <div className="diff-column original">
          <div className="diff-col-header">Original</div>
          <pre className="code-block">
            {origLines.map((line, idx) => (
              <div key={idx} className="code-line">
                <span className="line-num">{idx + 1}</span>
                <span className="line-content">{line}</span>
              </div>
            ))}
          </pre>
        </div>
        <div className="diff-column updated">
          <div className="diff-col-header">Proposed Fix</div>
          <pre className="code-block">
            {updatedLines.map((line, idx) => {
              const isDifferent = origLines[idx] !== line;
              return (
                <div
                  key={idx}
                  className={`code-line ${isDifferent ? 'modified-add' : ''}`}
                >
                  <span className="line-num">{idx + 1}</span>
                  <span className="line-content">{line}</span>
                </div>
              );
            })}
          </pre>
        </div>
      </div>
    );
  };

  return (
    <div className="diff-viewer">
      <div className="diff-tabs">
        {changes.map((file, idx) => (
          <button
            key={file.path}
            onClick={() => setActiveFileIndex(idx)}
            className={`diff-tab-btn ${idx === activeFileIndex ? 'active' : ''}`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <span className="file-path">{file.path}</span>
          </button>
        ))}
      </div>

      <div className="diff-content-wrapper">
        <div className="file-meta-bar">
          <span className="file-active-name">{activeFile.path}</span>
          <span className="file-badge">AI Suggested Changes</span>
        </div>
        {renderSimpleDiff(activeFile.original_content, activeFile.updated_content)}
      </div>
    </div>
  );
};
