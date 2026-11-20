import { api } from './client';
import type { ReviewRunItem, RunDetail, ApprovalDecision, ApproveResponse } from '../types/run';

export async function getRuns(repo?: string, prNumber?: number): Promise<ReviewRunItem[]> {
  const params = new URLSearchParams();
  if (repo) params.set('repo_full_name', repo);
  if (prNumber !== undefined && !isNaN(prNumber)) params.set('pr_number', prNumber.toString());

  const query = params.toString() ? `?${params.toString()}` : '';
  return api<ReviewRunItem[]>(`/runs${query}`);
}

export async function getRun(runId: string): Promise<RunDetail> {
  return api<RunDetail>(`/runs/${runId}`);
}

export async function submitApproval(
  runId: string,
  decision: ApprovalDecision,
  feedback: string = ''
): Promise<ApproveResponse> {
  return api<ApproveResponse>(`/runs/${runId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ decision, feedback }),
  });
}
