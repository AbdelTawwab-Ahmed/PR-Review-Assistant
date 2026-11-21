import { api } from './client';

export interface UserRepoItem {
  id: number;
  name: string;
  full_name: string;
  description: string | null;
  language: string;
  stars: number;
  forks: number;
  default_branch: string;
  updated_at: string;
  private: boolean;
}

export interface RepoOpenPR {
  number: number;
  title: string;
  author: string;
  avatar_url: string;
  head_sha: string;
  head_branch: string;
  base_branch: string;
  created_at: string;
}

export interface RepoDetailsResponse {
  repo: {
    id: number;
    name: string;
    full_name: string;
    description: string;
    stars: number;
    forks: number;
    language: string;
    default_branch: string;
    owner: {
      login: string;
      avatar_url?: string;
    };
    html_url?: string;
  };
  url_pr_number?: number | null;
  open_prs: RepoOpenPR[];
}

export interface AnalyzeRepoResponse {
  status: string;
  run_id: string;
  repo: string;
  pr_number: number;
  title: string;
  head_sha: string;
  dashboard_url: string;
}

export interface MonitoredReposResponse {
  repositories: string[];
  count: number;
}

export interface ListenRepoResponse {
  status: string;
  repo: string;
  dispatched_prs: number[];
  message: string;
}

export async function getUserRepos(): Promise<UserRepoItem[]> {
  return api<UserRepoItem[]>('/repos/user-repos');
}

export async function getRepoDetails(repo: string): Promise<RepoDetailsResponse> {
  const encoded = encodeURIComponent(repo);
  return api<RepoDetailsResponse>(`/repos/details?repo=${encoded}`);
}

export async function analyzeRepository(repo: string, prNumber?: number): Promise<AnalyzeRepoResponse> {
  return api<AnalyzeRepoResponse>('/repos/analyze', {
    method: 'POST',
    body: JSON.stringify({ repo, pr_number: prNumber }),
  });
}

export async function getListeningRepos(): Promise<MonitoredReposResponse> {
  return api<MonitoredReposResponse>('/repos/listening');
}

export async function startListeningRepo(repoUrl: string): Promise<ListenRepoResponse> {
  return api<ListenRepoResponse>('/repos/listen', {
    method: 'POST',
    body: JSON.stringify({ repo_url: repoUrl }),
  });
}

export async function stopListeningRepo(repo: string): Promise<{ status: string; repo: string }> {
  return api<{ status: string; repo: string }>('/repos/listen', {
    method: 'DELETE',
    body: JSON.stringify({ repo }),
  });
}
