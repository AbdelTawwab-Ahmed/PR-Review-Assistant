import React, { useState, useCallback } from 'react';
import type { RepoDetailsResponse } from '../api/repos';
import type { RunDetail } from '../types/run';
import { DashboardStateContext, type ActiveAnalysis } from './dashboardState';

export const DashboardStateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [inputVal, setInputVal] = useState('');
  const [selectedRepo, setSelectedRepo] = useState('');
  const [selectedPr, setSelectedPr] = useState<number | undefined>(undefined);
  const [repoDetails, setRepoDetails] = useState<RepoDetailsResponse | null>(null);

  const [activeAnalysis, setActiveAnalysis] = useState<ActiveAnalysis | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [completedRun, setCompletedRun] = useState<RunDetail | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [sessionRunIds, setSessionRunIds] = useState<string[]>([]);

  const registerSessionRun = useCallback((runId: string) => {
    if (!runId) return;
    setSessionRunIds((prev) => (prev.includes(runId) ? prev : [...prev, runId]));
  }, []);

  const clearSessionRuns = useCallback(() => {
    setSessionRunIds([]);
    setCompletedRun(null);
  }, []);

  return (
    <DashboardStateContext.Provider
      value={{
        inputVal,
        setInputVal,
        selectedRepo,
        setSelectedRepo,
        selectedPr,
        setSelectedPr,
        repoDetails,
        setRepoDetails,
        activeAnalysis,
        setActiveAnalysis,
        isAnalyzing,
        setIsAnalyzing,
        completedRun,
        setCompletedRun,
        analysisError,
        setAnalysisError,
        sessionRunIds,
        registerSessionRun,
        clearSessionRuns,
      }}
    >
      {children}
    </DashboardStateContext.Provider>
  );
};
