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
    <div className="modal-overlay">
      <div className="modal-container">
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="hitl-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div>
              <h3 className="modal-title">Human-in-the-Loop Review</h3>
              <p className="modal-subtitle">Review and authorize changes before they are applied</p>
            </div>
          </div>
          <button onClick={onClose} className="modal-close-btn" disabled={isLoading}>
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="decision-selector">
            <label
              className={`decision-option ${decision === 'approve' ? 'selected-approve' : ''}`}
            >
              <input
                type="radio"
                name="decision"
                value="approve"
                checked={decision === 'approve'}
                onChange={() => setDecision('approve')}
              />
              <div className="option-text">
                <span className="option-title">Approve & Publish</span>
                <span className="option-desc">Commit fixes to a new PR branch and publish for merge.</span>
              </div>
            </label>

            <label
              className={`decision-option ${decision === 'request_changes' ? 'selected-changes' : ''}`}
            >
              <input
                type="radio"
                name="decision"
                value="request_changes"
                checked={decision === 'request_changes'}
                onChange={() => setDecision('request_changes')}
              />
              <div className="option-text">
                <span className="option-title">Request Changes</span>
                <span className="option-desc">Instruct the AI agent to replan fixes with your feedback.</span>
              </div>
            </label>

            <label
              className={`decision-option ${decision === 'reject' ? 'selected-reject' : ''}`}
            >
              <input
                type="radio"
                name="decision"
                value="reject"
                checked={decision === 'reject'}
                onChange={() => setDecision('reject')}
              />
              <div className="option-text">
                <span className="option-title">Reject Proposal</span>
                <span className="option-desc">Discard this fix proposal without applying modifications.</span>
              </div>
            </label>
          </div>

          <div className="feedback-group">
            <label htmlFor="feedback-input" className="feedback-label">
              Feedback & Instructions {decision === 'request_changes' ? '(Required)' : '(Optional)'}
            </label>
            <textarea
              id="feedback-input"
              rows={4}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder={
                decision === 'request_changes'
                  ? 'Specify what needs to be changed in the proposed code...'
                  : 'Add notes for the team or PR description...'
              }
              required={decision === 'request_changes'}
              className="feedback-textarea"
            />
          </div>

          <div className="modal-actions">
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
              disabled={isLoading}
              className={`btn btn-primary ${decision}`}
            >
              {isLoading ? (
                <span className="btn-loading">
                  <span className="spinner" /> Submitting...
                </span>
              ) : decision === 'approve' ? (
                'Approve & Commit'
              ) : decision === 'request_changes' ? (
                'Request Changes'
              ) : (
                'Reject Proposal'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
