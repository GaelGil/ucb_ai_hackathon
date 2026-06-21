import type { ResearchType, ReviewFilter, SuggestionStatus, SuggestionType, TranslationReviewFilter } from "@/types/domain";

export const queryKeys = {
  datasets: ["datasets"] as const,
  workspace: (datasetId: string) => ["workspace", datasetId] as const,
  dashboard: (datasetId: string) => [...queryKeys.workspace(datasetId), "dashboard"] as const,
  suggestionsRoot: (datasetId: string, type: SuggestionType, status: SuggestionStatus) =>
    [...queryKeys.workspace(datasetId), "suggestions", type, status] as const,
  suggestions: (
    datasetId: string,
    type: SuggestionType,
    status: SuggestionStatus,
    limit: number,
    offset: number,
  ) => [...queryKeys.suggestionsRoot(datasetId, type, status), limit, offset] as const,
  annotationRowsRoot: (datasetId: string, type: SuggestionType) =>
    [...queryKeys.workspace(datasetId), "annotation-rows", type] as const,
  annotationRows: (
    datasetId: string,
    type: SuggestionType,
    limit: number,
    offset: number,
    reviewFilter: ReviewFilter = "all",
  ) => [...queryKeys.annotationRowsRoot(datasetId, type), limit, offset, reviewFilter] as const,
  labelsRoot: (datasetId: string, type: SuggestionType) => [...queryKeys.workspace(datasetId), "labels", type] as const,
  labels: (
    datasetId: string,
    type: SuggestionType,
    limit: number,
    offset: number,
    reviewFilter: TranslationReviewFilter = "all",
  ) => [...queryKeys.labelsRoot(datasetId, type), limit, offset, reviewFilter] as const,
  research: (datasetId: string, type: ResearchType) => [...queryKeys.workspace(datasetId), "research", type] as const,
};
