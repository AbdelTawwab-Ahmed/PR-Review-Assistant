import React, { useState } from 'react';
import type { ApprovalDecision } from '../types/run';

interface ApprovalModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (decision: ApprovalDecision, feedback: string) => Promise<void>;
  isLoading: boolean;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isLoading,
}) => {
  const [decision, setDecision] = useState<ApprovalDecision>('approve');
  const [feedback, setFeedback] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit(decision, feedback);
    onClose();
  };

  return (
    <div className="modal-backdrop-blur">
      <div className="modal-dialog-elevated">
        <div className="modal-header-section">
          <div className="modal-icon-badge">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2.2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div>
            <h3 className="modal-heading">Human-in-the-Loop Authorization</h3>
            <p className="modal-subheading">
              Review and authorize the AI agent's proposed remediation before publishing to GitHub
            </p>
          </div>
          <button onClick={onClose} className="modal-close-x" disabled={isLoading}>
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form-content">
          <div className="decision-cards-grid">
            <label className={`decision-card ${decision === 'approve' ? 'selected-approve' : ''}`}>
              <input
                type="radio"
                name="decision"
                value="approve"
                checked={decision === 'approve'}
                onChange={() => setDecision('approve')}
              />
              <div className="card-indicator" />
              <div className="card-body">
                <span className="card-title">✅ Approve & Push Fix</span>
                <span className="card-desc">
                  Authorize the changes. The agent will create a fix commit and push it to the PR branch.
                </span>
              </div>
            </label>

            <label className={`decision-card ${decision === 'request_changes' ? 'selected-changes' : ''}`}>
              <input
                type="radio"
                name="decision"
                value="request_changes"
                checked={decision === 'request_changes'}
                onChange={() => setDecision('request_changes')}
              />
              <div className="card-indicator" />
              <div className="card-body">
                <span className="card-title">🔄 Request Changes</span>
                <span className="card-desc">
                  Ask the multi-agent fixer to replan and adapt the solution using your feedback below.
                </span>
              </div>
            </label>

            <label className={`decision-card ${decision === 'reject' ? 'selected-reject' : ''}`}>
              <input
                type="radio"
                name="decision"
                value="reject"
                checked={decision === 'reject'}
                onChange={() => setDecision('reject')}
              />
              <div className="card-indicator" />
              <div className="card-body">
                <span className="card-title">⛔ Reject Proposal</span>
                <span className="card-desc">
                  Dismiss the proposed changes without modifying the PR branch or committing files.
                </span>
              </div>
            </label>
          </div>

          <div className="feedback-input-section">
            <label htmlFor="feedback-text" className="feedback-label-title">
              Guidance & Reviewer Notes {decision === 'request_changes' ? '(Required)' : '(Optional)'}
            </label>
            <textarea
              id="feedback-text"
              rows={3}
              placeholder={
                decision === 'request_changes'
                  ? 'Explain what the agent should modify or preserve...'
                  : 'Add optional review comments for the audit log...'
              }
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              className="feedback-textarea"
              required={decision === 'request_changes'}
            />
          </div>

          <div className="modal-action-buttons">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || (decision === 'request_changes' && !feedback.trim())}
              className={`btn ${decision === 'reject' ? 'btn-danger' : 'btn-primary'}`}
            >
              {isLoading ? (
                <>
                  <span className="spinner-sm" />
                  Broadcasting to Agent...
                </>
              ) : decision === 'approve' ? (
                'Confirm & Publish to GitHub'
              ) : decision === 'request_changes' ? (
                'Submit Feedback to Fixer'
              ) : (
                'Confirm Rejection'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
