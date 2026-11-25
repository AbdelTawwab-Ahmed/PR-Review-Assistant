import { createContext, useContext } from 'react';
import type { RepoDetailsResponse } from '../api/repos';
import type { RunDetail } from '../types/run';

export interface ActiveAnalysis {
  runId: string;
  repo: string;
  prNumber: number;
}

export interface DashboardStateContextValue {
  inputVal: string;
  setInputVal: (val: string) => void;
  selectedRepo: string;
  setSelectedRepo: (repo: string) => void;
  selectedPr: number | undefined;
  setSelectedPr: (pr: number | undefined) => void;
  repoDetails: RepoDetailsResponse | null;
  setRepoDetails: (details: RepoDetailsResponse | null) => void;
  activeAnalysis: ActiveAnalysis | null;
  setActiveAnalysis: (analysis: ActiveAnalysis | null) => void;
  isAnalyzing: boolean;
  setIsAnalyzing: (analyzing: boolean) => void;
  completedRun: RunDetail | null;
  setCompletedRun: (run: RunDetail | null) => void;
  analysisError: string | null;
  setAnalysisError: (err: string | null) => void;
  sessionRunIds: string[];
  registerSessionRun: (runId: string) => void;
  clearSessionRuns: () => void;
}

export const DashboardStateContext = createContext<DashboardStateContextValue | null>(null);

export function useDashboardState(): DashboardStateContextValue {
  const ctx = useContext(DashboardStateContext);
  if (!ctx) {
    throw new Error('useDashboardState must be used within a DashboardStateProvider');
  }
  return ctx;
}
