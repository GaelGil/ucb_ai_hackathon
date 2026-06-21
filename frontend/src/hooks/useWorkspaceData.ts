import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { EMPTY_DATASETS, EMPTY_LABELS, EMPTY_SUGGESTIONS, PAGE_SIZE } from "@/lib/constants";
import { queryKeys } from "@/lib/queryKeys";
import type {
  Dashboard,
  Dataset,
  LabelsResponse,
  PaginationMeta,
  ResearchArtifact,
  ResearchType,
  SuggestionsResponse,
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
  return data ?? { total: 0, limit: PAGE_SIZE, offset: pageIndex * PAGE_SIZE };
}

export function useWorkspaceData(
  datasetId: string,
  activeTab: WorkspaceTab,
  activeResearchType: ResearchType,
  pagination: WorkspacePagination,
) {
  const enabled = datasetId.length > 0;
  const researchPanelVisible = activeTab === "pos" || activeTab === "translate";
  const posOffset = pagination.posSuggestions * PAGE_SIZE;
  const ocrOffset = pagination.ocrSuggestions * PAGE_SIZE;
  const translationSuggestionOffset = pagination.translationSuggestions * PAGE_SIZE;
  const translationLabelOffset = pagination.translationLabels * PAGE_SIZE;
  const dashboardQuery = useQuery({
    queryKey: queryKeys.dashboard(datasetId),
    queryFn: ({ signal }) => api<Dashboard>(`/datasets/${datasetId}/dashboard`, { signal }),
    enabled,
  });
  const posSuggestionsQuery = useQuery({
    queryKey: queryKeys.suggestions(datasetId, "pos", "pending", PAGE_SIZE, posOffset),
    queryFn: ({ signal }) =>
      api<SuggestionsResponse>(
        `/datasets/${datasetId}/suggestions?type=pos&status=pending&limit=${PAGE_SIZE}&offset=${posOffset}`,
        { signal },
      ),
    enabled: enabled && activeTab === "pos",
  });
  const ocrSuggestionsQuery = useQuery({
    queryKey: queryKeys.suggestions(datasetId, "ocr", "pending", PAGE_SIZE, ocrOffset),
    queryFn: ({ signal }) =>
      api<SuggestionsResponse>(
        `/datasets/${datasetId}/suggestions?type=ocr&status=pending&limit=${PAGE_SIZE}&offset=${ocrOffset}`,
        { signal },
      ),
    enabled: enabled && activeTab === "ocr",
  });
  const translationSuggestionsQuery = useQuery({
    queryKey: queryKeys.suggestions(datasetId, "translation", "pending", PAGE_SIZE, translationSuggestionOffset),
    queryFn: ({ signal }) =>
      api<SuggestionsResponse>(
        `/datasets/${datasetId}/suggestions?type=translation&status=pending&limit=${PAGE_SIZE}&offset=${translationSuggestionOffset}`,
        { signal },
      ),
    enabled: enabled && activeTab === "translate",
  });
  const translationLabelsQuery = useQuery({
    queryKey: queryKeys.labels(datasetId, "translation", PAGE_SIZE, translationLabelOffset),
    queryFn: ({ signal }) =>
      api<LabelsResponse>(
        `/datasets/${datasetId}/labels?type=translation&limit=${PAGE_SIZE}&offset=${translationLabelOffset}`,
        { signal },
      ),
    enabled: enabled && activeTab === "translate",
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
    posSuggestionsQuery,
    ocrSuggestionsQuery,
    translationSuggestionsQuery,
    translationLabelsQuery,
    posResearchQuery,
    translationResearchQuery,
  ];

  return {
    dashboard: dashboardQuery.data ?? null,
    posSuggestions: posSuggestionsQuery.data?.suggestions ?? EMPTY_SUGGESTIONS,
    ocrSuggestions: ocrSuggestionsQuery.data?.suggestions ?? EMPTY_SUGGESTIONS,
    translationSuggestions: translationSuggestionsQuery.data?.suggestions ?? EMPTY_SUGGESTIONS,
    translationLabels: translationLabelsQuery.data?.labels ?? EMPTY_LABELS,
    posSuggestionsPage: pageMeta(posSuggestionsQuery.data, pagination.posSuggestions),
    ocrSuggestionsPage: pageMeta(ocrSuggestionsQuery.data, pagination.ocrSuggestions),
    translationSuggestionsPage: pageMeta(translationSuggestionsQuery.data, pagination.translationSuggestions),
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
