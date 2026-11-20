import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getRuns, getRun, submitApproval } from '../api/runs';
import type { ApprovalDecision } from '../types/run';

export function useRuns(repo?: string, prNumber?: number) {
  return useQuery({
    queryKey: ['runs', repo, prNumber],
    queryFn: () => getRuns(repo, prNumber),
    refetchInterval: 5000,
  });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: ['run', runId],
    queryFn: () => (runId ? getRun(runId) : Promise.reject('No runId')),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (
        status === 'ready_to_merge' ||
        status === 'rejected' ||
        status === 'failed' ||
        status === 'awaiting_approval'
      ) {
        return false;
      }
      return 3000;
    },
  });
}

export function useApproveRun(runId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ decision, feedback }: { decision: ApprovalDecision; feedback?: string }) =>
      submitApproval(runId, decision, feedback),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['run', runId] });
      queryClient.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}
