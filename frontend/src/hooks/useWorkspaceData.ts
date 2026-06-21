import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { EMPTY_ANNOTATION_ROWS, EMPTY_DATASETS, EMPTY_LABELS, EMPTY_SUGGESTIONS, PAGE_SIZE } from "@/lib/constants";
import { queryKeys } from "@/lib/queryKeys";
import type {
  AnnotationRowsResponse,
  Dashboard,
  Dataset,
  LabelsResponse,
  PaginationMeta,
  ResearchArtifact,
  ResearchType,
  ReviewFilter,
  SuggestionsResponse,
  TranslationReviewFilter,
  WorkspacePagination,
  WorkspaceTab,
} from "@/types/domain";

export function useDatasets() {
  return useQuery({
    queryKey: queryKeys.datasets,
    queryFn: ({ signal }) => api<Dataset[]>("/datasets", { signal }),
  });
}

function pageMeta(data: PaginationMeta | undefined, pageIndex: number): PaginationMeta {
  const limit = data?.limit || PAGE_SIZE;
  return {
    total: data?.total ?? 0,
    limit,
    offset: pageIndex * limit,
  };
}

export function useWorkspaceData(
  datasetId: string,
  activeTab: WorkspaceTab,
  activeResearchType: ResearchType,
  pagination: WorkspacePagination,
  posReviewFilter: ReviewFilter,
  translationReviewFilter: TranslationReviewFilter,
) {
  const enabled = datasetId.length > 0;
  const researchPanelVisible = activeTab === "pos" || activeTab === "translate";
  const posOffset = pagination.posRows * PAGE_SIZE;
  const ocrOffset = pagination.ocrSuggestions * PAGE_SIZE;
  const translationLabelOffset = pagination.translationLabels * PAGE_SIZE;
  const dashboardQuery = useQuery({
    queryKey: queryKeys.dashboard(datasetId),
    queryFn: ({ signal }) => api<Dashboard>(`/datasets/${datasetId}/dashboard`, { signal }),
    enabled,
  });
  const posRowsQuery = useQuery({
    queryKey: queryKeys.annotationRows(datasetId, "pos", PAGE_SIZE, posOffset, posReviewFilter),
    queryFn: ({ signal }) =>
      api<AnnotationRowsResponse>(
        `/datasets/${datasetId}/annotation-rows?type=pos&limit=${PAGE_SIZE}&offset=${posOffset}&needs_review=${posReviewFilter === "needs_review"}`,
        { signal },
      ),
    enabled: enabled && activeTab === "pos",
    placeholderData: keepPreviousData,
  });
  const ocrSuggestionsQuery = useQuery({
    queryKey: queryKeys.suggestions(datasetId, "ocr", "pending", PAGE_SIZE, ocrOffset),
    queryFn: ({ signal }) =>
      api<SuggestionsResponse>(
        `/datasets/${datasetId}/suggestions?type=ocr&status=pending&limit=${PAGE_SIZE}&offset=${ocrOffset}`,
        { signal },
      ),
    enabled: enabled && activeTab === "ocr",
    placeholderData: keepPreviousData,
  });
  const translationLabelsQuery = useQuery({
    queryKey: queryKeys.labels(datasetId, "translation", PAGE_SIZE, translationLabelOffset, translationReviewFilter),
    queryFn: ({ signal }) =>
      api<LabelsResponse>(
        `/datasets/${datasetId}/labels?type=translation&limit=${PAGE_SIZE}&offset=${translationLabelOffset}&needs_review=${translationReviewFilter === "needs_review"}`,
        { signal },
      ),
    enabled: enabled && activeTab === "translate",
    placeholderData: keepPreviousData,
  });
  const posResearchQuery = useQuery({
    queryKey: queryKeys.research(datasetId, "pos"),
    queryFn: ({ signal }) => api<ResearchArtifact | null>(`/datasets/${datasetId}/research?type=pos`, { signal }),
    enabled: enabled && researchPanelVisible && activeResearchType === "pos",
  });
  const translationResearchQuery = useQuery({
    queryKey: queryKeys.research(datasetId, "translation"),
    queryFn: ({ signal }) =>
      api<ResearchArtifact | null>(`/datasets/${datasetId}/research?type=translation`, { signal }),
    enabled:
      enabled &&
      researchPanelVisible &&
      (activeTab === "translate" || activeResearchType === "translation"),
  });
  const queries = [
    dashboardQuery,
    posRowsQuery,
    ocrSuggestionsQuery,
    translationLabelsQuery,
    posResearchQuery,
    translationResearchQuery,
  ];

  return {
    dashboard: dashboardQuery.data ?? null,
    posRows: posRowsQuery.data?.rows ?? EMPTY_ANNOTATION_ROWS,
    ocrSuggestions: ocrSuggestionsQuery.data?.suggestions ?? EMPTY_SUGGESTIONS,
    translationLabels: translationLabelsQuery.data?.labels ?? EMPTY_LABELS,
    posRowsPage: pageMeta(posRowsQuery.data, pagination.posRows),
    ocrSuggestionsPage: pageMeta(ocrSuggestionsQuery.data, pagination.ocrSuggestions),
    translationLabelsPage: pageMeta(translationLabelsQuery.data, pagination.translationLabels),
    researchByType: {
      pos: posResearchQuery.data ?? null,
      translation: translationResearchQuery.data ?? null,
    } satisfies Record<ResearchType, ResearchArtifact | null>,
    isLoading: queries.some(query => query.isLoading),
    isFetching: queries.some(query => query.isFetching),
    error: queries.find(query => query.error)?.error ?? null,
  };
}
