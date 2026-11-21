import { api } from './client';

export interface MonitoredReposResponse {
  repositories: string[];
  count: number;
}

export interface ListenRepoResponse {
  status: string;
  input: string;
  dispatched_prs: number[];
  message: string;
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
