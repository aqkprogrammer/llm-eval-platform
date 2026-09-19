import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  CaseResult,
  Comparison,
  Dataset,
  DatasetSummary,
  Experiment,
  ExperimentCreate,
  ExperimentSummary,
  Health,
  LeaderboardRow,
  MetricInfo,
  ModelConfig,
  ModelConfigCreate,
  MonitoringOverview,
  Page,
  PromptPreview,
  PromptPreviewRequest,
  PromptTemplate,
  PromptTemplateCreate,
  PromptVersion,
  PromptVersionCreate,
  ProvidersResponse,
  Stats,
  Trace,
  TraceSummary,
} from "./types";

export const ACTIVE_STATUSES = new Set(["queued", "running"]);

// ------------------------------------------------------------------ system
export const useHealth = () =>
  useQuery({ queryKey: ["health"], queryFn: () => api.get<Health>("/health"), refetchInterval: 30_000 });

export const useStats = () => useQuery({ queryKey: ["stats"], queryFn: () => api.get<Stats>("/stats") });

export const useMetrics = () =>
  useQuery({ queryKey: ["metrics"], queryFn: () => api.get<MetricInfo[]>("/metrics"), staleTime: 5 * 60_000 });

// ------------------------------------------------------------------ experiments
export const useExperiments = (limit = 100) =>
  useQuery({
    queryKey: ["experiments", limit],
    queryFn: () => api.get<ExperimentSummary[]>("/experiments", { limit }),
    refetchInterval: (q) => (q.state.data?.some((e) => ACTIVE_STATUSES.has(e.status)) ? 2000 : false),
  });

export const useExperiment = (id: string | undefined) =>
  useQuery({
    queryKey: ["experiment", id],
    queryFn: () => api.get<Experiment>(`/experiments/${id}`),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data && ACTIVE_STATUSES.has(q.state.data.status) ? 1500 : false),
  });

export interface ResultsFilter {
  variant_id?: string;
  passed?: boolean;
  limit: number;
  offset: number;
}

export const useResults = (id: string | undefined, filter: ResultsFilter, live: boolean) =>
  useQuery({
    queryKey: ["results", id, filter],
    queryFn: () => api.get<Page<CaseResult>>(`/experiments/${id}/results`, { ...filter }),
    enabled: !!id,
    placeholderData: keepPreviousData,
    refetchInterval: live ? 3000 : false,
  });

export function useCreateExperiment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ExperimentCreate) => api.post<Experiment>("/experiments", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["experiments"] });
      void qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useCancelExperiment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Experiment>(`/experiments/${id}/cancel`),
    onSuccess: (data) => {
      qc.setQueryData(["experiment", data.id], data);
      void qc.invalidateQueries({ queryKey: ["experiments"] });
    },
  });
}

export interface CompareParams {
  baseline: string;
  candidate: string;
  baseline_variant?: string;
  candidate_variant?: string;
  tolerance?: number;
}

export const useComparison = (p: CompareParams | null) =>
  useQuery({
    queryKey: ["compare", p],
    queryFn: () => api.get<Comparison>("/compare", { ...p! }),
    enabled: !!p,
  });

export const useLeaderboard = (datasetId?: string) =>
  useQuery({
    queryKey: ["leaderboard", datasetId ?? null],
    queryFn: () => api.get<{ rows: LeaderboardRow[] }>("/leaderboard", { dataset_id: datasetId }),
  });

// ------------------------------------------------------------------ datasets
export const useDatasets = () =>
  useQuery({ queryKey: ["datasets"], queryFn: () => api.get<DatasetSummary[]>("/datasets") });

export const useDataset = (id: string | undefined) =>
  useQuery({ queryKey: ["dataset", id], queryFn: () => api.get<Dataset>(`/datasets/${id}`), enabled: !!id });

export function useImportDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) => api.post<Dataset>("/datasets/import", form),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["datasets"] });
      void qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

// ------------------------------------------------------------------ prompts
export const usePrompts = () =>
  useQuery({ queryKey: ["prompts"], queryFn: () => api.get<PromptTemplate[]>("/prompts") });

export function useCreatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PromptTemplateCreate) => api.post<PromptTemplate>("/prompts", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["prompts"] });
      void qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useCreatePromptVersion(templateId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PromptVersionCreate) => api.post<PromptVersion>(`/prompts/${templateId}/versions`, body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export const usePromptPreview = (req: PromptPreviewRequest | null) =>
  useQuery({
    queryKey: ["prompt-preview", req],
    queryFn: () => api.post<PromptPreview>("/prompts/preview", req),
    enabled: !!req && req.user_template.trim().length > 0,
    placeholderData: keepPreviousData,
    retry: false,
  });

// ------------------------------------------------------------------ models
export const useModels = () => useQuery({ queryKey: ["models"], queryFn: () => api.get<ModelConfig[]>("/models") });

export const useProviders = () =>
  useQuery({ queryKey: ["providers"], queryFn: () => api.get<ProvidersResponse>("/providers") });

export function useCreateModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ModelConfigCreate) => api.post<ModelConfig>("/models", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["models"] });
      void qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useDeleteModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/models/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["models"] });
      void qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

// ------------------------------------------------------------------ traces
export interface TraceFilter {
  source?: string;
  model?: string;
  flagged?: boolean;
  limit: number;
  offset: number;
}

export const useTraces = (filter: TraceFilter) =>
  useQuery({
    queryKey: ["traces", filter],
    queryFn: () => api.get<Page<TraceSummary>>("/traces", { ...filter }),
    placeholderData: keepPreviousData,
  });

export const useTrace = (id: string | undefined) =>
  useQuery({
    queryKey: ["trace", id],
    queryFn: () => api.get<Trace>(`/traces/${id}`),
    enabled: !!id,
    refetchInterval: (q) => {
      const s = q.state.data?.score_status;
      return s === "pending" || s === "running" ? 1500 : false;
    },
  });

// ------------------------------------------------------------------ monitoring
export const useMonitoring = (window: string, buckets: number, model?: string) =>
  useQuery({
    queryKey: ["monitoring", window, buckets, model ?? null],
    queryFn: () => api.get<MonitoringOverview>("/monitoring/overview", { window, buckets, model }),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
