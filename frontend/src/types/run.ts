export type RunStatus =
  | 'pending'
  | 'analyzing'
  | 'awaiting_plan_approval'
  | 'planning'
  | 'fixing'
  | 'validating'
  | 'awaiting_approval'
  | 'updating_pr'
  | 'ready_to_merge'
  | 'rejected'
  | 'failed';

export type ApprovalDecision = 'approve' | 'reject' | 'request_changes';

export type Severity = 'low' | 'medium' | 'high' | 'critical';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface RiskFactor {
  name: string;
  points: number;
  reason: string;
}

export interface RiskReport {
  score: number;
  level: RiskLevel;
  factors: RiskFactor[];
}

export interface Finding {
  id?: string;
  category: string;
  severity: Severity;
  title: string;
  description: string;
  file_path: string | null;
  line_start: number | null;
  line_end: number | null;
  suggestion: string;
  source?: string;
}

export interface FileChange {
  path: string;
  original_content?: string;
  updated_content?: string;
  old_content?: string;
  new_content?: string;
}

export interface FixAction {
  file_path: string;
  description: string;
  finding_ids: string[];
}

export interface FixPlan {
  actions: FixAction[];
  rationale: string;
  attempt: number;
}

export interface FixProposal {
  plan_summary?: string;
  summary?: string;
  changes: FileChange[];
  explanation?: string;
  status?: string;
}

export interface ReviewRunItem {
  id: string;
  repo_full_name: string;
  pr_number: number;
  head_sha: string;
  status: RunStatus;
  created_at?: string;
  updated_at?: string;
  risk?: RiskReport | null;
  findings?: Finding[];
  fix_plan?: FixPlan | null;
}

export interface RunDetail {
  run_id: string;
  status: RunStatus;
  repo_full_name: string;
  pr_number: number;
  head_sha: string;
  findings_count: number;
  risk: RiskReport | null;
  proposal: FixProposal | null;
  approval_decision: ApprovalDecision | null;
  published_branch: string | null;
  published_pr_url: string | null;
  notes: string[];
  findings?: Finding[];
  fix_plan?: FixPlan | null;
  interrupt_payload?: {
    type?: string;
    message?: string;
    proposal?: FixProposal;
    [key: string]: unknown;
  } | null;
}

export interface ApproveResponse {
  run_id: string;
  decision: ApprovalDecision;
  status: string;
  published_branch: string | null;
  published_pr_url: string | null;
  notes: string[];
}
