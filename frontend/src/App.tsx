import {
  ActionIcon,
  AppShell,
  Badge,
  Box,
  Button,
  Card,
  Divider,
  FileInput,
  Grid,
  Group,
  Loader,
  Modal,
  Paper,
  Pagination,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Textarea,
  TextInput,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  TbDatabase,
  TbFileText,
  TbLayoutSidebarLeftCollapse,
  TbPlus,
  TbTags,
  TbTrash,
  TbUpload,
  TbWand,
} from "react-icons/tb";

const configuredApiBaseUrl =
  typeof process !== "undefined" ? process.env.BUN_PUBLIC_API_BASE_URL?.replace(/\/$/, "") : "";
const isLocalBrowser =
  typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE_URL = configuredApiBaseUrl || (isLocalBrowser ? "http://127.0.0.1:8000" : "");
const PAGE_SIZE = 10;

const UPOS_TAGS = [
  "ADJ",
  "ADP",
  "ADV",
  "AUX",
  "CCONJ",
  "DET",
  "INTJ",
  "NOUN",
  "NUM",
  "PART",
  "PRON",
  "PROPN",
  "PUNCT",
  "SCONJ",
  "SYM",
  "VERB",
  "X",
] as const;

const UI = {
  background: "#030304",
  header: "rgba(7, 7, 8, 0.96)",
  navbar: "#09090b",
  panel: "rgba(18, 18, 22, 0.96)",
  panelSoft: "rgba(14, 14, 18, 0.84)",
  border: "rgba(255, 255, 255, 0.11)",
};

const SIDEBAR_WIDTH = 304;
const SIDEBAR_COLLAPSED_WIDTH = 84;

type SourceType = "text" | "csv" | "txt" | "pdf" | "image";
type ImportKind = "generic" | "translation" | "pos";
type ResearchType = "pos" | "translation";
type SuggestionType = "pos" | "ocr" | "translation" | "emotion" | "intention" | "text" | "custom";
type SuggestionStatus = "pending" | "accepted" | "denied" | "updated" | "approved" | "edited";
type LabelSource = "csv_import" | "human" | "ai_accepted" | "ai_updated";

type ProviderWarning = {
  provider: string;
  stage: string;
  message: string;
  fallback: boolean;
};

type Dataset = {
  id: string;
  name: string;
  language_code: string;
  language_name: string;
};

type ImportRecord = {
  id: string;
  dataset_id: string;
  source_type: SourceType;
  filename: string | null;
  item_count: number;
  asset_count: number;
  label_count: number;
  status: string;
  column_mapping: Record<string, unknown>;
  created_at: string;
};

type ResearchArtifact = {
  id: string;
  type: ResearchType;
  summary: string;
  guidelines: string[];
  sources: { title: string; url: string; excerpt: string }[];
  warnings: ProviderWarning[];
};

type TokenSuggestion = {
  index: number;
  token: string;
  suggested_pos: string;
  confidence: number;
  rationale: string;
};

type Suggestion = {
  id: string;
  type: SuggestionType;
  status: SuggestionStatus;
  original_text: string;
  suggested_text: string | null;
  tokens: TokenSuggestion[];
  confidence: number;
  rationale: string;
};

type Label = {
  id: string;
  dataset_id: string;
  data_row_id: string;
  data_text: string | null;
  import_id: string | null;
  ai_suggestion_id: string | null;
  type: SuggestionType;
  name: string | null;
  value: Record<string, unknown>;
  source: LabelSource;
  original_column_name: string | null;
  created_at: string;
};

type PaginationMeta = {
  total: number;
  limit: number;
  offset: number;
};

type SuggestionsResponse = PaginationMeta & {
  suggestions: Suggestion[];
};

type LabelsResponse = PaginationMeta & {
  labels: Label[];
};

type WorkspacePagination = {
  posSuggestions: number;
  ocrSuggestions: number;
  translationSuggestions: number;
  translationLabels: number;
};

type PosModel = {
  status: string;
  mode: "demo" | "real";
  minimum_examples_met: boolean;
  accepted_sentence_count: number;
  minimum_examples: number;
  model_name: string | null;
  metrics: Record<string, number>;
};

type Dashboard = {
  dataset: Dataset;
  imports: ImportRecord[];
  research: ResearchArtifact | null;
  suggestion_counts: Record<string, number>;
  item_count: number;
  pos_model: PosModel;
};

type Job = {
  id: string;
  type: string;
  status: string;
  progress: number;
  message: string;
  error: string | null;
  metadata: Record<string, unknown>;
};

type DetailRow = {
  label: string;
  value: ReactNode;
};

type DetailContent = {
  title: string;
  rows: DetailRow[];
};

type Toast = {
  tone: "violet" | "red" | "green";
  message: string;
};

type DraftMap = Record<string, TokenSuggestion[]>;
type TextDraftMap = Record<string, string>;
type WorkspaceTab = "pos" | "ocr" | "translate" | "upload" | "models";

const EMPTY_DATASETS: Dataset[] = [];
const EMPTY_SUGGESTIONS: Suggestion[] = [];
const EMPTY_LABELS: Label[] = [];

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (options?.body !== undefined && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: headers.entries().next().done ? undefined : headers,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

const queryKeys = {
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
  labelsRoot: (datasetId: string, type: SuggestionType) => [...queryKeys.workspace(datasetId), "labels", type] as const,
  labels: (datasetId: string, type: SuggestionType, limit: number, offset: number) =>
    [...queryKeys.labelsRoot(datasetId, type), limit, offset] as const,
  research: (datasetId: string, type: ResearchType) => [...queryKeys.workspace(datasetId), "research", type] as const,
};

function useDatasets() {
  return useQuery({
    queryKey: queryKeys.datasets,
    queryFn: ({ signal }) => api<Dataset[]>("/datasets", { signal }),
  });
}

function pageMeta(data: PaginationMeta | undefined, pageIndex: number): PaginationMeta {
  return data ?? { total: 0, limit: PAGE_SIZE, offset: pageIndex * PAGE_SIZE };
}

function useWorkspaceData(
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
      api<LabelsResponse>(`/datasets/${datasetId}/labels?type=translation&limit=${PAGE_SIZE}&offset=${translationLabelOffset}`, {
        signal,
      }),
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

function sourceColor(source: SourceType) {
  switch (source) {
    case "text":
    case "txt":
      return "green";
    case "csv":
      return "violet";
    case "pdf":
      return "red";
    case "image":
      return "grape";
  }
}

function statusColor(status: string) {
  switch (status) {
    case "accepted":
    case "approved":
    case "ready":
    case "succeeded":
      return "green";
    case "updated":
    case "edited":
    case "running":
      return "violet";
    case "denied":
    case "failed":
      return "red";
    case "pending":
    case "queued":
      return "yellow";
    default:
      return "gray";
  }
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

const IMPORT_KIND_OPTIONS = [
  { value: "generic", label: "Generic CSV" },
  { value: "translation", label: "Translation labels" },
  { value: "pos", label: "POS tags" },
] satisfies { value: ImportKind; label: string }[];

function csvFormatHint(importKind: ImportKind) {
  if (importKind === "translation") {
    return "Required columns: text,translation,source,src,target. Extra metadata columns are allowed.";
  }
  if (importKind === "pos") {
    return "CSV columns: text,tags. Tags must be UPOS values matching text tokens.";
  }
  return "Generic CSV uses text as the sentence column and creates labels from other columns.";
}

function importSuccessMessage(base: string, job: Job) {
  if (isJobActive(job)) {
    return `${base.replace(/ imported$/, " import")} started`;
  }
  const skipped = Number(job.metadata.skipped_count ?? 0);
  if (!Number.isFinite(skipped) || skipped <= 0) {
    return base;
  }
  return `${base}; skipped ${skipped} row${skipped === 1 ? "" : "s"}`;
}

function isJobActive(job: Job) {
  return job.status === "queued" || job.status === "running";
}

function lastPageIndex(total: number) {
  return Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
}

function assertJobSucceeded(job: Job) {
  if (job.status === "failed") {
    throw new Error(job.error || "Import failed");
  }
}

export function App() {
  const queryClient = useQueryClient();
  const datasetsQuery = useDatasets();
  const datasets = datasetsQuery.data ?? EMPTY_DATASETS;
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("upload");
  const [activeResearchType, setActiveResearchType] = useState<ResearchType>("pos");
  const [posSuggestionsPage, setPosSuggestionsPage] = useState(0);
  const [ocrSuggestionsPage, setOcrSuggestionsPage] = useState(0);
  const [translationSuggestionsPage, setTranslationSuggestionsPage] = useState(0);
  const [translationLabelsPage, setTranslationLabelsPage] = useState(0);
  const workspaceData = useWorkspaceData(selectedDatasetId, activeTab, activeResearchType, {
    posSuggestions: posSuggestionsPage,
    ocrSuggestions: ocrSuggestionsPage,
    translationSuggestions: translationSuggestionsPage,
    translationLabels: translationLabelsPage,
  });
  const dashboard = workspaceData.dashboard;
  const suggestions = workspaceData.posSuggestions;
  const ocrSuggestions = workspaceData.ocrSuggestions;
  const translationSuggestions = workspaceData.translationSuggestions;
  const translationLabels = workspaceData.translationLabels;
  const researchByType = workspaceData.researchByType;
  const [jobs, setJobs] = useState<Job[]>([]);
  const [working, setWorking] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [addLanguageFormOpen, setAddLanguageFormOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Dataset | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<DetailContent | null>(null);

  const [datasetName, setDatasetName] = useState("");
  const [languageCode, setLanguageCode] = useState("");
  const [languageName, setLanguageName] = useState("");
  const [manualText, setManualText] = useState("");
  const [manualSource, setManualSource] = useState<SourceType>("text");
  const [manualImportKind, setManualImportKind] = useState<ImportKind>("generic");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileImportKind, setFileImportKind] = useState<ImportKind>("generic");
  const [tokenDrafts, setTokenDrafts] = useState<DraftMap>({});
  const [ocrDrafts, setOcrDrafts] = useState<TextDraftMap>({});
  const [translationDrafts, setTranslationDrafts] = useState<TextDraftMap>({});

  const selectedDataset = useMemo(
    () => datasets.find(dataset => dataset.id === selectedDatasetId) ?? datasets[0] ?? null,
    [datasets, selectedDatasetId],
  );

  const latestAssetImport = useMemo(
    () => dashboard?.imports.find(item => item.source_type === "pdf" || item.source_type === "image") ?? null,
    [dashboard?.imports],
  );

  const acceptedPosCount =
    (dashboard?.suggestion_counts["pos:accepted"] ?? 0) +
    (dashboard?.suggestion_counts["pos:updated"] ?? 0) +
    (dashboard?.suggestion_counts["pos:approved"] ?? 0) +
    (dashboard?.suggestion_counts["pos:edited"] ?? 0);
  const uploadFileIsCsv = uploadFile?.name.toLowerCase().endsWith(".csv") ?? false;
  const datasetsLoading = datasetsQuery.isLoading;
  const workspaceLoading = workspaceData.isLoading;
  const activeJobIds = useMemo(() => jobs.filter(isJobActive).map(job => job.id).join(","), [jobs]);

  useEffect(() => {
    if (!datasetsQuery.isSuccess) return;
    setSelectedDatasetId(current =>
      datasets.some(dataset => dataset.id === current) ? current : datasets[0]?.id || "",
    );
  }, [datasets, datasetsQuery.isSuccess]);

  useEffect(() => {
    setPosSuggestionsPage(0);
    setOcrSuggestionsPage(0);
    setTranslationSuggestionsPage(0);
    setTranslationLabelsPage(0);
    if (!selectedDatasetId) {
      clearWorkspaceState();
    }
  }, [selectedDatasetId]);

  useEffect(() => {
    setPosSuggestionsPage(current => Math.min(current, lastPageIndex(workspaceData.posSuggestionsPage.total)));
  }, [workspaceData.posSuggestionsPage.total]);

  useEffect(() => {
    setOcrSuggestionsPage(current => Math.min(current, lastPageIndex(workspaceData.ocrSuggestionsPage.total)));
  }, [workspaceData.ocrSuggestionsPage.total]);

  useEffect(() => {
    setTranslationSuggestionsPage(current =>
      Math.min(current, lastPageIndex(workspaceData.translationSuggestionsPage.total)),
    );
  }, [workspaceData.translationSuggestionsPage.total]);

  useEffect(() => {
    setTranslationLabelsPage(current => Math.min(current, lastPageIndex(workspaceData.translationLabelsPage.total)));
  }, [workspaceData.translationLabelsPage.total]);

  useEffect(() => {
    if (datasetsQuery.error) {
      showError(datasetsQuery.error);
    }
  }, [datasetsQuery.error]);

  useEffect(() => {
    if (workspaceData.error) {
      showError(workspaceData.error);
    }
  }, [workspaceData.error]);

  useEffect(() => {
    const jobIds = activeJobIds.split(",").filter(Boolean);
    if (jobIds.length === 0) return;
    let cancelled = false;

    async function refreshJobs() {
      try {
        const responses = await Promise.all(jobIds.map(jobId => api<{ job: Job }>(`/jobs/${jobId}`)));
        if (cancelled) return;
        const updates = new Map(responses.map(response => [response.job.id, response.job]));
        const completed = responses.some(response => !isJobActive(response.job));
        setJobs(previous => previous.map(job => updates.get(job.id) ?? job));
        if (completed && selectedDatasetId) {
          await invalidateDashboard(selectedDatasetId);
        }
      } catch (error) {
        if (!cancelled) {
          showError(error);
        }
      }
    }

    void refreshJobs();
    const interval = window.setInterval(() => void refreshJobs(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [activeJobIds, selectedDatasetId]);

  useEffect(() => {
    setTokenDrafts(previous => {
      const next = { ...previous };
      for (const suggestion of suggestions) {
        next[suggestion.id] ??= suggestion.tokens;
      }
      return next;
    });
  }, [suggestions]);

  useEffect(() => {
    setOcrDrafts(previous => {
      const next = { ...previous };
      for (const suggestion of ocrSuggestions) {
        next[suggestion.id] ??= suggestion.suggested_text ?? "";
      }
      return next;
    });
  }, [ocrSuggestions]);

  useEffect(() => {
    setTranslationDrafts(previous => {
      const next = { ...previous };
      for (const suggestion of translationSuggestions) {
        next[suggestion.id] ??= suggestion.suggested_text ?? "";
      }
      return next;
    });
  }, [translationSuggestions]);

  async function invalidateDatasets() {
    await queryClient.invalidateQueries({ queryKey: queryKeys.datasets });
  }

  async function invalidateDashboard(datasetId = selectedDatasetId) {
    if (!datasetId) return;
    await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard(datasetId) });
  }

  async function invalidateTranslationLabels(datasetId = selectedDatasetId) {
    if (!datasetId) return;
    setTranslationLabelsPage(0);
    await queryClient.invalidateQueries({ queryKey: queryKeys.labelsRoot(datasetId, "translation") });
  }

  async function invalidateSuggestions(type: SuggestionType, datasetId = selectedDatasetId) {
    if (!datasetId) return;
    if (type === "pos") {
      setPosSuggestionsPage(0);
    }
    if (type === "ocr") {
      setOcrSuggestionsPage(0);
    }
    if (type === "translation") {
      setTranslationSuggestionsPage(0);
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.suggestionsRoot(datasetId, type, "pending") });
  }

  async function invalidateResearch(type: ResearchType, datasetId = selectedDatasetId) {
    if (!datasetId) return;
    await queryClient.invalidateQueries({ queryKey: queryKeys.research(datasetId, type) });
  }

  async function invalidateImportResult(importKind: ImportKind, datasetId = selectedDatasetId) {
    await invalidateDashboard(datasetId);
    if (importKind === "translation") {
      await invalidateTranslationLabels(datasetId);
    }
  }

  async function runAction<T>(
    callback: () => Promise<T>,
    successMessage: string | ((result: T) => string),
    afterSuccess: (result: T) => Promise<void> | void = () => invalidateDashboard(),
  ) {
    setWorking(true);
    try {
      const result = await callback();
      setToast({ tone: "green", message: typeof successMessage === "function" ? successMessage(result) : successMessage });
      await afterSuccess(result);
      return result;
    } catch (error) {
      showError(error);
      return null;
    } finally {
      setWorking(false);
    }
  }

  async function createDataset() {
    if (!datasetName.trim() || !languageCode.trim() || !languageName.trim()) return;
    await runAction(
      () =>
        api<Dataset>("/datasets", {
          method: "POST",
          body: JSON.stringify({
            name: datasetName.trim(),
            language_code: languageCode.trim(),
            language_name: languageName.trim(),
          }),
        }),
      "Dataset created",
      async created => {
        queryClient.setQueryData<Dataset[]>(queryKeys.datasets, current => [
          ...(current ?? []).filter(dataset => dataset.id !== created.id),
          created,
        ]);
        setSelectedDatasetId(created.id);
        setAddLanguageFormOpen(false);
        await invalidateDatasets();
      },
    );
  }

  async function deleteDataset(dataset: Dataset) {
    setWorking(true);
    try {
      await api<void>(`/datasets/${dataset.id}`, { method: "DELETE" });
      const remaining = datasets.filter(item => item.id !== dataset.id);
      const currentStillExists = remaining.some(item => item.id === selectedDatasetId);
      const nextSelectedId = currentStillExists ? selectedDatasetId : remaining[0]?.id || "";

      queryClient.setQueryData<Dataset[]>(queryKeys.datasets, remaining);
      queryClient.removeQueries({ queryKey: queryKeys.workspace(dataset.id) });
      setSelectedDatasetId(nextSelectedId);
      setDeleteTarget(null);
      setToast({ tone: "green", message: "Language deleted" });
      setJobs([]);
      await invalidateDatasets();

      if (!nextSelectedId) {
        clearWorkspaceState();
      }
    } catch (error) {
      showError(error);
    } finally {
      setWorking(false);
    }
  }

  async function importManualText() {
    if (!selectedDatasetId || !manualText.trim()) return;
    const importKind = manualSource === "csv" ? manualImportKind : "generic";
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/imports`, {
        method: "POST",
        body: JSON.stringify({ text: manualText, source_type: manualSource, import_kind: importKind }),
      });
      rememberJob(response.job);
      assertJobSucceeded(response.job);
      return response;
    }, response => importSuccessMessage(importKind === "generic" ? "Text imported" : "CSV labels imported", response.job), () =>
      invalidateImportResult(importKind),
    );
  }

  async function importFile() {
    if (!selectedDatasetId || !uploadFile) return;
    const form = new FormData();
    form.append("file", uploadFile);
    form.append("import_kind", fileImportKind);
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/imports`, {
        method: "POST",
        body: form,
      });
      rememberJob(response.job);
      assertJobSucceeded(response.job);
      setUploadFile(null);
      return response;
    }, response => importSuccessMessage(fileImportKind === "generic" ? "File imported" : "CSV labels imported", response.job), () =>
      invalidateImportResult(fileImportKind),
    );
  }

  async function runResearch(force = false, researchType = activeResearchType) {
    if (!selectedDatasetId) return;
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/research?type=${researchType}&force=${force}`, {
        method: "POST",
      });
      rememberJob(response.job);
      return response;
    }, force ? `${researchType.toUpperCase()} research refreshed` : `${researchType.toUpperCase()} research ready`, async () => {
      await invalidateResearch(researchType);
      await invalidateDashboard();
    });
  }

  async function generatePosSuggestions() {
    if (!selectedDatasetId) return;
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/pos-suggestions`, {
        method: "POST",
        body: JSON.stringify({ limit: 5 }),
      });
      rememberJob(response.job);
      assertJobSucceeded(response.job);
      return response;
    }, "Generated POS suggestions", async () => {
      await invalidateSuggestions("pos");
      await invalidateDashboard();
    });
  }

  async function generateTranslationSuggestions() {
    if (!selectedDatasetId) return;
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/translation-suggestions`, {
        method: "POST",
        body: JSON.stringify({ limit: 5 }),
      });
      rememberJob(response.job);
      assertJobSucceeded(response.job);
      return response;
    }, "Generated translation suggestions", async () => {
      await invalidateSuggestions("translation");
      await invalidateDashboard();
    });
  }

  async function runOcr() {
    if (!selectedDatasetId) return;
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/ocr`, {
        method: "POST",
        body: JSON.stringify({ import_id: latestAssetImport?.id ?? null }),
      });
      rememberJob(response.job);
      return response;
    }, "OCR suggestions generated", async () => {
      await invalidateSuggestions("ocr");
      await invalidateDashboard();
    });
  }

  async function reviewSuggestion(suggestion: Suggestion, action: SuggestionStatus) {
    await runAction(async () => {
      const payload =
        action === "updated" && suggestion.type === "pos"
          ? { action, edited_tokens: tokenDrafts[suggestion.id] ?? suggestion.tokens }
          : action === "updated" && suggestion.type === "translation"
            ? { action, edited_text: translationDrafts[suggestion.id] ?? suggestion.suggested_text ?? "" }
          : action === "updated"
            ? { action, edited_text: ocrDrafts[suggestion.id] ?? suggestion.suggested_text ?? "" }
              : { action };
      return api<Suggestion>(`/suggestions/${suggestion.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    }, action === "accepted" ? "Suggestion accepted" : action === "denied" ? "Suggestion denied" : "Suggestion updated", async () => {
      await invalidateSuggestions(suggestion.type);
      if (suggestion.type === "translation") {
        await invalidateTranslationLabels();
      }
      await invalidateDashboard();
    });
  }

  async function trainPosModel() {
    if (!selectedDatasetId) return;
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/pos-model/train`, {
        method: "POST",
        body: JSON.stringify({ minimum_examples: 20, demo_override: true }),
      });
      rememberJob(response.job);
      return response;
    }, "POS model trigger completed", () => invalidateDashboard());
  }

  function rememberJob(job: Job) {
    setJobs(previous => [job, ...previous.filter(item => item.id !== job.id)].slice(0, 5));
  }

  function openDetail(detail: DetailContent) {
    setSelectedDetail(detail);
  }

  function clearWorkspaceState() {
    setTokenDrafts({});
    setOcrDrafts({});
    setTranslationDrafts({});
    setJobs([]);
  }

  function updateTokenDraft(suggestionId: string, tokenIndex: number, tag: string | null) {
    if (!tag) return;
    setTokenDrafts(previous => {
      const current = previous[suggestionId] ?? [];
      return {
        ...previous,
        [suggestionId]: current.map(token =>
          token.index === tokenIndex ? { ...token, suggested_pos: tag } : token,
        ),
      };
    });
  }

  function showError(error: unknown) {
    setToast({ tone: "red", message: error instanceof Error ? error.message : "Request failed" });
  }

  function handleTabChange(value: string | null) {
    if (value === "pos" || value === "ocr" || value === "translate" || value === "upload" || value === "models") {
      setActiveTab(value);
      if (value === "pos") {
        setActiveResearchType("pos");
      }
      if (value === "translate") {
        setActiveResearchType("translation");
      }
    }
  }

  return (
    <>
      <Modal
        centered
        onClose={() => setDeleteTarget(null)}
        opened={deleteTarget !== null}
        title="Delete Language"
      >
        <Stack gap="md">
          <Text c="dimmed" size="sm">
            Delete {deleteTarget?.language_name ?? "this language"} and remove its imports, labels, research, jobs,
            and model state.
          </Text>
          <Group justify="flex-end">
            <Button color="gray" disabled={working} onClick={() => setDeleteTarget(null)} variant="subtle">
              Cancel
            </Button>
            <Button
              color="red"
              disabled={working || !deleteTarget}
              leftSection={<TbTrash aria-hidden="true" size={16} />}
              onClick={() => {
                if (deleteTarget) {
                  void deleteDataset(deleteTarget);
                }
              }}
            >
              Delete Language
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        centered
        onClose={() => setSelectedDetail(null)}
        opened={selectedDetail !== null}
        scrollAreaComponent={ScrollArea.Autosize}
        size="lg"
        title={selectedDetail?.title ?? "Details"}
      >
        <Stack gap="md">
          {selectedDetail?.rows.map(row => (
            <Box key={row.label}>
              <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                {row.label}
              </Text>
              {typeof row.value === "string" || typeof row.value === "number" ? (
                <Text size="sm" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                  {row.value}
                </Text>
              ) : (
                row.value
              )}
            </Box>
          ))}
        </Stack>
      </Modal>

      <AppShell
      layout="alt"
      header={{ height: 64 }}
      navbar={{
        width: sidebarCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH,
        breakpoint: "sm",
        collapsed: { mobile: false },
      }}
      padding={0}
    >
      <AppShell.Header
        style={{
          background: UI.header,
          borderBottom: `1px solid ${UI.border}`,
        }}
      >
        <Group h="100%" px="md" wrap="nowrap">
          <Title order={1} size="h3" lh={1.1} lineClamp={1}>
            {selectedDataset?.language_name ?? "Language"}
          </Title>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar
        style={{
          background: UI.navbar,
          borderRight: `1px solid ${UI.border}`,
        }}
      >
        <Stack gap="sm" h="100%" p="sm">
          {sidebarCollapsed ? (
            <Stack align="center" gap="sm" py="xs">
              <Tooltip label="Expand Sidebar" position="right">
                <ActionIcon
                  aria-label="Expand sidebar"
                  color="violet"
                  onClick={() => setSidebarCollapsed(false)}
                  radius="md"
                  size={46}
                  variant="filled"
                >
                  <Text fw={850} size="sm">
                    LB
                  </Text>
                </ActionIcon>
              </Tooltip>
            </Stack>
          ) : (
            <Group justify="space-between" wrap="nowrap" py="xs">
              <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                <ThemeIcon color="violet" radius="md" size={42} variant="filled">
                  LB
                </ThemeIcon>
                <Box style={{ minWidth: 0 }}>
                  <Text fw={850} lh={1} size="lg" truncate="end">
                    LangBase
                  </Text>
                  <Text c="dimmed" size="xs" truncate="end">
                    Low-resource AI workspace
                  </Text>
                </Box>
              </Group>
              <Tooltip label="Collapse Sidebar">
                <ActionIcon
                  aria-label="Collapse sidebar"
                  color="gray"
                  onClick={() => setSidebarCollapsed(true)}
                  size={38}
                  variant="subtle"
                >
                  <TbLayoutSidebarLeftCollapse aria-hidden="true" size={20} />
                </ActionIcon>
              </Tooltip>
            </Group>
          )}

          <ScrollArea flex={1} type="hover">
            <Stack align={sidebarCollapsed ? "center" : "stretch"} gap={6}>
              {!sidebarCollapsed ? (
                <Box px="xs" py={4}>
                  <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                    Languages
                  </Text>
                </Box>
              ) : null}
              {datasetsLoading ? (
                sidebarCollapsed ? (
                  <ActionIcon aria-label="Loading languages" disabled radius="md" size={46} variant="subtle">
                    <Loader color="violet" size="xs" />
                  </ActionIcon>
                ) : (
                  <Group gap="xs" px="xs" py="sm">
                    <Loader color="violet" size="xs" />
                    <Text c="dimmed" size="sm">
                      Loading languages…
                    </Text>
                  </Group>
                )
              ) : datasets.length === 0 ? (
                <Text c="dimmed" px={sidebarCollapsed ? 0 : "xs"} size="sm" ta={sidebarCollapsed ? "center" : "left"}>
                  {sidebarCollapsed ? "None" : "No languages yet."}
                </Text>
              ) : (
                datasets.map(dataset =>
                  sidebarCollapsed ? (
                    <Tooltip
                      key={dataset.id}
                      label={`${dataset.language_name} · ${dataset.name}`}
                      position="right"
                    >
                      <ActionIcon
                        aria-label={`Select ${dataset.language_name}`}
                        color={dataset.id === selectedDataset?.id ? "green" : "gray"}
                        onClick={() => setSelectedDatasetId(dataset.id)}
                        radius="md"
                        size={46}
                        variant={dataset.id === selectedDataset?.id ? "filled" : "light"}
                      >
                        <Text fw={800} size="xs">
                          {dataset.language_code.slice(0, 2).toUpperCase()}
                        </Text>
                      </ActionIcon>
                    </Tooltip>
                  ) : (
                    <Group
                      key={dataset.id}
                      align="stretch"
                      gap={6}
                      wrap="nowrap"
                    >
                      <Button
                        color={dataset.id === selectedDataset?.id ? "green" : "gray"}
                        fullWidth
                        justify="flex-start"
                        leftSection={
                          <ThemeIcon
                            color={dataset.id === selectedDataset?.id ? "green" : "violet"}
                            radius="md"
                            size={34}
                            variant={dataset.id === selectedDataset?.id ? "filled" : "light"}
                          >
                            {dataset.language_code.slice(0, 2).toUpperCase()}
                          </ThemeIcon>
                        }
                        onClick={() => setSelectedDatasetId(dataset.id)}
                        style={{ flex: 1, height: "auto", minWidth: 0, paddingBottom: 8, paddingTop: 8 }}
                        variant={dataset.id === selectedDataset?.id ? "light" : "subtle"}
                      >
                        <Box style={{ minWidth: 0, textAlign: "left" }}>
                          <Text fw={700} size="sm" truncate="end">
                            {dataset.name}
                          </Text>
                          <Text c="dimmed" size="xs" truncate="end">
                            {dataset.language_name} · {dataset.language_code}
                          </Text>
                        </Box>
                      </Button>
                      <Tooltip label={`Delete ${dataset.language_name}`}>
                        <ActionIcon
                          aria-label={`Delete ${dataset.language_name}`}
                          color="red"
                          disabled={working}
                          onClick={() => setDeleteTarget(dataset)}
                          radius="md"
                          size={42}
                          variant="subtle"
                        >
                          <TbTrash aria-hidden="true" size={18} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  ),
                )
              )}
            </Stack>
          </ScrollArea>

          {!sidebarCollapsed ? (
            <>
              <Divider />
              <Group justify="space-between" wrap="nowrap">
                <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                  New Language
                </Text>
                <Button
                  color="gray"
                  onClick={() => setAddLanguageFormOpen(current => !current)}
                  size="compact-xs"
                  type="button"
                  variant="subtle"
                >
                  {addLanguageFormOpen ? "Hide Form" : "Show Form"}
                </Button>
              </Group>
              {addLanguageFormOpen ? (
                <Box
                  component="form"
                  onSubmit={event => {
                    event.preventDefault();
                    void createDataset();
                  }}
                >
                  <Stack gap="xs">
                    <TextInput
                      autoComplete="off"
                      label="Dataset"
                      name="datasetName"
                      onChange={event => setDatasetName(event.currentTarget.value)}
                      placeholder="Dataset name"
                      size="xs"
                      value={datasetName}
                    />
                    <Group grow>
                      <TextInput
                        autoComplete="off"
                        label="Code"
                        name="languageCode"
                        onChange={event => setLanguageCode(event.currentTarget.value)}
                        placeholder="Language code"
                        size="xs"
                        spellCheck={false}
                        value={languageCode}
                      />
                      <TextInput
                        autoComplete="off"
                        label="Language"
                        name="languageName"
                        onChange={event => setLanguageName(event.currentTarget.value)}
                        placeholder="Language name"
                        size="xs"
                        value={languageName}
                      />
                    </Group>
                    <Button
                      color="green"
                      disabled={working || !datasetName.trim() || !languageCode.trim() || !languageName.trim()}
                      leftSection={<TbPlus aria-hidden="true" size={15} />}
                      size="xs"
                      type="submit"
                    >
                      Create Language
                    </Button>
                  </Stack>
                </Box>
              ) : null}
            </>
          ) : null}
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main style={{ background: UI.background, minHeight: "100vh" }}>
        <Box id="workspace-main" w="100%" maw={1480} mx="auto" px={{ base: "sm", sm: "lg" }} py="lg">
          <Stack gap="lg">
            {toast ? (
              <Paper
                aria-live="polite"
                withBorder
                p="sm"
                radius="md"
                style={{ background: UI.panelSoft, borderColor: `var(--mantine-color-${toast.tone}-6)` }}
              >
                <Group justify="space-between">
                  <Text size="sm">{toast.message}</Text>
                  <Button color="violet" size="compact-xs" variant="subtle" onClick={() => setToast(null)}>
                    Dismiss
                  </Button>
                </Group>
              </Paper>
            ) : null}

            {selectedDataset ? (
            <>
            {activeTab === "pos" || activeTab === "translate" ? (
              <Grid gutter="md">
                <Grid.Col span={{ base: 12, lg: 8 }}>
                  <ResearchPanel
                    activeType={activeResearchType}
                    research={researchByType[activeResearchType]}
                    working={working}
                    onOpenDetail={openDetail}
                    onResearch={() => void runResearch(false)}
                    onRefreshResearch={() => void runResearch(true)}
                    onTypeChange={setActiveResearchType}
                  />
                </Grid.Col>
                <Grid.Col span={{ base: 12, lg: 4 }}>
                  <JobsPanel jobs={jobs} />
                </Grid.Col>
              </Grid>
            ) : null}
            <Tabs value={activeTab} onChange={handleTabChange} radius="md" variant="pills">
              <Tabs.List>
                <Tabs.Tab leftSection={<TbTags aria-hidden="true" size={16} />} value="pos">
                  POS
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbWand aria-hidden="true" size={16} />} value="ocr">
                  OCR
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbFileText aria-hidden="true" size={16} />} value="translate">
                  Translate
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbUpload aria-hidden="true" size={16} />} value="upload">
                  Upload
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbDatabase aria-hidden="true" size={16} />} value="models">
                  Models
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="pos" pt="md">
                <PosSuggestionsTable
                  suggestions={suggestions}
                  tokenDrafts={tokenDrafts}
                  pagination={workspaceData.posSuggestionsPage}
                  pageIndex={posSuggestionsPage}
                  loading={workspaceLoading}
                  working={working}
                  onGenerate={() => void generatePosSuggestions()}
                  onOpenDetail={openDetail}
                  onPageChange={setPosSuggestionsPage}
                  onReview={(suggestion, action) => void reviewSuggestion(suggestion, action)}
                  onTokenChange={updateTokenDraft}
                />
              </Tabs.Panel>

              <Tabs.Panel value="ocr" pt="md">
                <OcrSuggestionsTable
                  latestAssetImport={latestAssetImport}
                  suggestions={ocrSuggestions}
                  drafts={ocrDrafts}
                  pagination={workspaceData.ocrSuggestionsPage}
                  pageIndex={ocrSuggestionsPage}
                  loading={workspaceLoading}
                  working={working}
                  onOpenDetail={openDetail}
                  onPageChange={setOcrSuggestionsPage}
                  onRunOcr={() => void runOcr()}
                  onDraftChange={(id, value) => setOcrDrafts(previous => ({ ...previous, [id]: value }))}
                  onReview={(suggestion, action) => void reviewSuggestion(suggestion, action)}
                />
              </Tabs.Panel>

              <Tabs.Panel value="translate" pt="md">
                <TranslationTable
                  labels={translationLabels}
                  suggestions={translationSuggestions}
                  drafts={translationDrafts}
                  labelsPagination={workspaceData.translationLabelsPage}
                  suggestionsPagination={workspaceData.translationSuggestionsPage}
                  labelsPageIndex={translationLabelsPage}
                  suggestionsPageIndex={translationSuggestionsPage}
                  research={researchByType.translation}
                  loading={workspaceLoading}
                  working={working}
                  onGenerate={() => void generateTranslationSuggestions()}
                  onOpenDetail={openDetail}
                  onLabelsPageChange={setTranslationLabelsPage}
                  onSuggestionsPageChange={setTranslationSuggestionsPage}
                  onDraftChange={(id, value) => setTranslationDrafts(previous => ({ ...previous, [id]: value }))}
                  onReview={(suggestion, action) => void reviewSuggestion(suggestion, action)}
                />
              </Tabs.Panel>

              <Tabs.Panel value="upload" pt="md">
                <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
                  <PaperPanel title="Manual Sentences" eyebrow="Text import">
                    <Stack gap="md">
                      <Select
                        data={[
                          { value: "text", label: "Manual text" },
                          { value: "csv", label: "CSV text" },
                          { value: "txt", label: "TXT lines" },
                        ]}
                        label="Source type"
                        name="manualSource"
                        value={manualSource}
                        onChange={value => setManualSource((value as SourceType | null) ?? "text")}
                      />
                      {manualSource === "csv" ? (
                        <>
                          <Select
                            data={IMPORT_KIND_OPTIONS}
                            label="CSV format"
                            name="manualImportKind"
                            value={manualImportKind}
                            onChange={value => setManualImportKind((value as ImportKind | null) ?? "generic")}
                          />
                          <Text c="dimmed" size="xs">
                            {csvFormatHint(manualImportKind)}
                          </Text>
                        </>
                      ) : null}
                      <Textarea
                        autoComplete="off"
                        autosize
                        label="Sentences"
                        minRows={8}
                        name="manualText"
                        onChange={event => setManualText(event.currentTarget.value)}
                        placeholder="Enter one sentence per line…"
                        value={manualText}
                      />
                      <Button
                        color="green"
                        disabled={working || !manualText.trim()}
                        leftSection={<TbFileText aria-hidden="true" size={16} />}
                        onClick={() => void importManualText()}
                      >
                        {working ? "Importing..." : "Import Sentences"}
                      </Button>
                    </Stack>
                  </PaperPanel>

                  <PaperPanel title="Files and Imports" eyebrow="CSV, TXT, PDF, image">
                    <Stack gap="md">
                      <Select
                        data={IMPORT_KIND_OPTIONS}
                        label="CSV format"
                        name="fileImportKind"
                        value={fileImportKind}
                        onChange={value => setFileImportKind((value as ImportKind | null) ?? "generic")}
                      />
                      <Text
                        c={fileImportKind !== "generic" && uploadFile && !uploadFileIsCsv ? "red" : "dimmed"}
                        size="xs"
                      >
                        {fileImportKind !== "generic" && uploadFile && !uploadFileIsCsv
                          ? "Translation and POS label imports require a .csv file."
                          : csvFormatHint(fileImportKind)}
                      </Text>
                      <Group align="end" wrap="wrap">
                        <FileInput
                          flex={1}
                          label="Upload file"
                          name="uploadFile"
                          placeholder="Choose CSV, TXT, PDF, or image…"
                          value={uploadFile}
                          onChange={setUploadFile}
                        />
                        <Button
                          color="green"
                          disabled={working || !uploadFile || (fileImportKind !== "generic" && !uploadFileIsCsv)}
                          leftSection={<TbUpload aria-hidden="true" size={16} />}
                          onClick={() => void importFile()}
                        >
                          {working ? "Uploading..." : "Upload"}
                        </Button>
                      </Group>
                      <ImportsTable imports={dashboard?.imports ?? []} loading={workspaceLoading} />
                    </Stack>
                  </PaperPanel>
                </SimpleGrid>
              </Tabs.Panel>

              <Tabs.Panel value="models" pt="md">
                <ModelsPanel
                  acceptedPosCount={acceptedPosCount}
                  posModel={dashboard?.pos_model ?? null}
                  working={working}
                  onTrainPos={() => void trainPosModel()}
                />
              </Tabs.Panel>
            </Tabs>
            </>
            ) : datasetsLoading ? (
              <Paper withBorder radius="md" p="lg" style={{ background: UI.panel, borderColor: UI.border }}>
                <LoadingBlock message="Loading workspace data…" />
              </Paper>
            ) : (
              <EmptyState
                title="No backend data yet"
                message="Create a language from the sidebar or import data once a language exists."
              />
            )}
          </Stack>
        </Box>
      </AppShell.Main>
      </AppShell>
    </>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <Card
      withBorder
      radius="md"
      p="md"
      style={{ background: UI.panel, borderColor: UI.border }}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Box>
          <Text c="dimmed" fw={700} size="xs" tt="uppercase">
            {label}
          </Text>
          <Text fw={850} mt={4}>
            {value}
          </Text>
        </Box>
        <ThemeIcon color={tone} radius="md" variant="light">
          {label.slice(0, 2)}
        </ThemeIcon>
      </Group>
    </Card>
  );
}

function PaperPanel({ title, eyebrow, children }: { title: string; eyebrow: string; children: ReactNode }) {
  return (
    <Paper
      withBorder
      radius="md"
      p="lg"
      style={{ background: UI.panel, borderColor: UI.border }}
    >
      <Stack gap="md">
        <Box>
          <Text c="dimmed" fw={700} size="xs" tt="uppercase">
            {eyebrow}
          </Text>
          <Title order={3} size="h3">
            {title}
          </Title>
        </Box>
        {children}
      </Stack>
    </Paper>
  );
}

function LoadingBlock({ message = "Loading data…" }: { message?: string }) {
  return (
    <Group gap="sm" py="lg">
      <Loader color="violet" size="sm" />
      <Text c="dimmed" size="sm">
        {message}
      </Text>
    </Group>
  );
}

function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <Paper withBorder radius="md" p="lg" style={{ background: UI.panel, borderColor: UI.border }}>
      <Stack gap={4}>
        <Title order={3} size="h4">
          {title}
        </Title>
        <Text c="dimmed" size="sm">
          {message}
        </Text>
      </Stack>
    </Paper>
  );
}

function CompactPanel({ title, eyebrow, children }: { title: string; eyebrow: string; children: ReactNode }) {
  return (
    <Paper withBorder radius="md" p="md" h="100%" style={{ background: UI.panel, borderColor: UI.border }}>
      <Stack gap="sm" h="100%">
        <Box>
          <Text c="dimmed" fw={700} size="xs" tt="uppercase">
            {eyebrow}
          </Text>
          <Title order={3} size="h4">
            {title}
          </Title>
        </Box>
        {children}
      </Stack>
    </Paper>
  );
}

function PreviewTextButton({
  text,
  title,
  onOpen,
  fw = 700,
}: {
  text: string | null | undefined;
  title: string;
  onOpen: () => void;
  fw?: number;
}) {
  const value = text?.trim() || "No text";
  return (
    <Button
      aria-label={`View ${title}`}
      color="gray"
      h="auto"
      justify="start"
      onClick={onOpen}
      p={0}
      radius="sm"
      variant="subtle"
      w="100%"
      styles={{
        inner: { justifyContent: "flex-start", minWidth: 0 },
        label: { minWidth: 0, whiteSpace: "normal", width: "100%" },
      }}
    >
      <Text fw={fw} lineClamp={2} size="sm" style={{ minWidth: 0, overflowWrap: "anywhere", textAlign: "left" }}>
        {value}
      </Text>
    </Button>
  );
}

function formatTokenDetails(tokens: TokenSuggestion[]) {
  if (tokens.length === 0) return "No tokens";
  return tokens
    .map(token => `${token.index + 1}. ${token.token} -> ${token.suggested_pos} (${formatPercent(token.confidence)})`)
    .join("\n");
}

function ResearchPanel({
  activeType,
  research,
  working,
  onOpenDetail,
  onResearch,
  onRefreshResearch,
  onTypeChange,
}: {
  activeType: ResearchType;
  research: ResearchArtifact | null;
  working: boolean;
  onOpenDetail: (detail: DetailContent) => void;
  onResearch: () => void;
  onRefreshResearch: () => void;
  onTypeChange: (type: ResearchType) => void;
}) {
  const title = activeType === "pos" ? "POS research" : "Translation research";
  return (
    <CompactPanel title="Cached Research Notes" eyebrow="Dataset + language + task">
      <Stack gap="sm">
        <Group align="end" gap="xs" wrap="wrap">
          <Select
            data={[
              { value: "pos", label: "POS" },
              { value: "translation", label: "Translation" },
            ]}
            label="Research type"
            name="researchType"
            onChange={value => onTypeChange((value as ResearchType | null) ?? "pos")}
            value={activeType}
            w={180}
          />
          <Button disabled={working} onClick={onResearch}>
            {research ? `Use Cached ${title}` : `Run ${title}`}
          </Button>
          <Button color="green" disabled={working} onClick={onRefreshResearch} variant="light">
            Refresh
          </Button>
        </Group>
        {research ? (
          <>
            <Group gap="xs">
              <Badge color="violet" radius="sm" variant="light">
                {research.guidelines.length} Guidelines
              </Badge>
              <Badge color="gray" radius="sm" variant="light">
                {research.sources.length} Sources
              </Badge>
              {research.warnings.length > 0 ? (
                <Badge color="yellow" radius="sm" variant="light">
                  {research.warnings.length} Warnings
                </Badge>
              ) : null}
            </Group>
            <Text lineClamp={2} size="sm" style={{ overflowWrap: "anywhere" }}>
              {research.summary}
            </Text>
            <Button
              color="violet"
              onClick={() =>
                onOpenDetail({
                  title,
                  rows: [
                    { label: "Summary", value: research.summary },
                    { label: "Guidelines", value: research.guidelines.join("\n") || "No guidelines" },
                    {
                      label: "Sources",
                      value:
                        research.sources.map(source => `${source.title}\n${source.url}\n${source.excerpt}`).join("\n\n") ||
                        "No sources",
                    },
                    {
                      label: "Warnings",
                      value:
                        research.warnings
                          .map(warning => `${warning.provider} ${warning.stage}: ${warning.message}`)
                          .join("\n") || "No warnings",
                    },
                  ],
                })
              }
              size="compact-sm"
              variant="light"
              w="fit-content"
            >
              View Details
            </Button>
          </>
        ) : (
          <Text c="dimmed" size="sm">
            {title} has not been generated for this workspace yet.
          </Text>
        )}
      </Stack>
    </CompactPanel>
  );
}

function SuggestionActions({
  suggestion,
  working,
  onReview,
}: {
  suggestion: Suggestion;
  working: boolean;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
}) {
  return (
    <Group gap="xs">
      <Button color="green" disabled={working} onClick={() => onReview(suggestion, "accepted")} size="compact-xs">
        Approve
      </Button>
      <Button
        color="violet"
        disabled={working}
        onClick={() => onReview(suggestion, "updated")}
        size="compact-xs"
        variant="light"
      >
        Save Edit
      </Button>
      <Button color="red" disabled={working} onClick={() => onReview(suggestion, "denied")} size="compact-xs" variant="light">
        Deny
      </Button>
    </Group>
  );
}

function PaginatedTableFooter({
  pagination,
  pageIndex,
  onPageChange,
}: {
  pagination: PaginationMeta;
  pageIndex: number;
  onPageChange: (pageIndex: number) => void;
}) {
  if (pagination.total <= 0) {
    return null;
  }

  const limit = Math.max(pagination.limit || PAGE_SIZE, 1);
  const pageCount = Math.max(1, Math.ceil(pagination.total / limit));
  const start = Math.min(pagination.offset + 1, pagination.total);
  const end = Math.min(pagination.offset + limit, pagination.total);

  return (
    <Group justify="space-between" wrap="wrap">
      <Text c="dimmed" size="sm">
        Showing {start}-{end} of {pagination.total}
      </Text>
      {pageCount > 1 ? (
        <Pagination
          color="violet"
          onChange={value => onPageChange(value - 1)}
          radius="md"
          size="sm"
          total={pageCount}
          value={Math.min(pageIndex + 1, pageCount)}
        />
      ) : null}
    </Group>
  );
}

function PosSuggestionsTable({
  suggestions,
  tokenDrafts,
  pagination,
  pageIndex,
  loading,
  working,
  onGenerate,
  onOpenDetail,
  onPageChange,
  onReview,
  onTokenChange,
}: {
  suggestions: Suggestion[];
  tokenDrafts: DraftMap;
  pagination: PaginationMeta;
  pageIndex: number;
  loading: boolean;
  working: boolean;
  onGenerate: () => void;
  onOpenDetail: (detail: DetailContent) => void;
  onPageChange: (pageIndex: number) => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
  onTokenChange: (suggestionId: string, tokenIndex: number, tag: string | null) => void;
}) {
  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<Suggestion>();

    return [
      columnHelper.accessor("original_text", {
        header: "Text",
        cell: info => (
          <Box maw={260} miw={180}>
            <PreviewTextButton
              text={info.getValue()}
              title="POS Text"
              onOpen={() => {
                const suggestion = info.row.original;
                const tokens = tokenDrafts[suggestion.id] ?? suggestion.tokens;
                onOpenDetail({
                  title: "POS Suggestion",
                  rows: [
                    { label: "Text", value: suggestion.original_text },
                    { label: "Status", value: suggestion.status },
                    { label: "Confidence", value: formatPercent(suggestion.confidence) },
                    { label: "Rationale", value: suggestion.rationale || "No rationale" },
                    { label: "Tokens", value: formatTokenDetails(tokens) },
                    { label: "Suggestion ID", value: suggestion.id },
                  ],
                });
              }}
            />
            <Badge color={statusColor(info.row.original.status)} mt={6} radius="sm" variant="dot">
              {info.row.original.status}
            </Badge>
          </Box>
        ),
      }),
      columnHelper.display({
        id: "tags",
        header: "Tags",
        cell: info => {
          const suggestion = info.row.original;
          const tokens = tokenDrafts[suggestion.id] ?? suggestion.tokens;

          return (
            <Stack gap={6} miw={220}>
              {tokens.slice(0, 8).map(token => (
                <Group key={`${suggestion.id}-${token.index}`} gap={6} wrap="nowrap">
                  <Badge color="gray" radius="sm" variant="light">
                    {token.token}
                  </Badge>
                  <Select
                    aria-label={`UPOS tag for ${token.token}`}
                    data={UPOS_TAGS.map(tag => ({ value: tag, label: tag }))}
                    name={`upos-${suggestion.id}-${token.index}`}
                    onChange={value => onTokenChange(suggestion.id, token.index, value)}
                    size="xs"
                    value={token.suggested_pos}
                    w={96}
                  />
                </Group>
              ))}
              {tokens.length > 8 ? (
                <Button
                  color="gray"
                  onClick={() =>
                    onOpenDetail({
                      title: "POS Tokens",
                      rows: [
                        { label: "Text", value: suggestion.original_text },
                        { label: "Tokens", value: formatTokenDetails(tokens) },
                      ],
                    })
                  }
                  size="compact-xs"
                  variant="subtle"
                  w="fit-content"
                >
                  View {tokens.length - 8} More
                </Button>
              ) : null}
            </Stack>
          );
        },
      }),
      columnHelper.display({
        id: "suggestions",
        header: "Suggestions",
        cell: info => {
          const suggestion = info.row.original;

          return (
            <Stack gap="xs" miw={260}>
              <Group gap="xs">
                <Badge color="grape" radius="sm" variant="light">
                  {formatPercent(suggestion.confidence)}
                </Badge>
                <Text c="dimmed" size="xs">
                  AI suggestion
                </Text>
              </Group>
              <Text c="dimmed" size="xs">
                {suggestion.rationale || "Review the suggested UPOS tags."}
              </Text>
              <SuggestionActions suggestion={suggestion} working={working} onReview={onReview} />
            </Stack>
          );
        },
      }),
    ];
  }, [onOpenDetail, onReview, onTokenChange, tokenDrafts, working]);

  const table = useReactTable({
    columns,
    data: suggestions,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <PaperPanel title="POS Tagging" eyebrow="Text, tags, suggestions">
      <Stack gap="md">
        <Group justify="space-between">
          <Text c="dimmed" size="sm">
            Pending rows: {pagination.total}
          </Text>
          <Button disabled={working} onClick={onGenerate}>
            Generate 5 Suggestions
          </Button>
        </Group>
        {loading ? (
          <LoadingBlock message="Loading POS suggestions…" />
        ) : suggestions.length === 0 ? (
          <Text c="dimmed" size="sm">
            No pending POS suggestions. Generate a batch after uploading text.
          </Text>
        ) : (
          <ScrollArea type="auto">
            <Table miw={920} highlightOnHover>
              <Table.Thead>
                {table.getHeaderGroups().map(headerGroup => (
                  <Table.Tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <Table.Th key={header.id}>
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </Table.Th>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Thead>
              <Table.Tbody>
                {table.getRowModel().rows.map(row => (
                  <Table.Tr key={row.id}>
                    {row.getVisibleCells().map(cell => (
                      <Table.Td key={cell.id} style={{ verticalAlign: "top" }}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </Table.Td>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
        <PaginatedTableFooter pagination={pagination} pageIndex={pageIndex} onPageChange={onPageChange} />
      </Stack>
    </PaperPanel>
  );
}

function ImportsTable({ imports, loading = false }: { imports: ImportRecord[]; loading?: boolean }) {
  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<ImportRecord>();

    return [
      columnHelper.accessor("source_type", {
        header: "Source",
        cell: info => (
          <Badge color={sourceColor(info.getValue())} radius="sm" variant="light">
            {info.getValue()}
          </Badge>
        ),
      }),
      columnHelper.accessor(row => row.filename ?? "manual import", {
        id: "file",
        header: "File",
        cell: info => (
          <Text maw={280} size="sm" truncate="end">
            {info.getValue()}
          </Text>
        ),
      }),
      columnHelper.accessor(row => row.item_count || row.asset_count, {
        id: "items",
        header: "Items",
        cell: info => (
          <Text size="sm" style={{ fontVariantNumeric: "tabular-nums" }}>
            {new Intl.NumberFormat().format(info.getValue())}
          </Text>
        ),
      }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: info => (
          <Badge color={statusColor(info.getValue())} radius="sm" variant="dot">
            {info.getValue()}
          </Badge>
        ),
      }),
    ];
  }, []);

  const table = useReactTable({
    columns,
    data: imports,
    getCoreRowModel: getCoreRowModel(),
  });

  if (loading) {
    return <LoadingBlock message="Loading imports…" />;
  }

  if (imports.length === 0) {
    return (
      <Text c="dimmed" size="sm">
        No imports yet.
      </Text>
    );
  }
  return (
    <ScrollArea type="auto">
      <Table miw={620} highlightOnHover>
        <Table.Thead>
          {table.getHeaderGroups().map(headerGroup => (
            <Table.Tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <Table.Th key={header.id}>
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </Table.Th>
              ))}
            </Table.Tr>
          ))}
        </Table.Thead>
        <Table.Tbody>
          {table.getRowModel().rows.map(row => (
            <Table.Tr key={row.id}>
              {row.getVisibleCells().map(cell => (
                <Table.Td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  );
}

function OcrSuggestionsTable({
  latestAssetImport,
  suggestions,
  drafts,
  pagination,
  pageIndex,
  loading,
  working,
  onOpenDetail,
  onPageChange,
  onRunOcr,
  onDraftChange,
  onReview,
}: {
  latestAssetImport: ImportRecord | null;
  suggestions: Suggestion[];
  drafts: TextDraftMap;
  pagination: PaginationMeta;
  pageIndex: number;
  loading: boolean;
  working: boolean;
  onOpenDetail: (detail: DetailContent) => void;
  onPageChange: (pageIndex: number) => void;
  onRunOcr: () => void;
  onDraftChange: (id: string, value: string) => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
}) {
  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<Suggestion>();

    return [
      columnHelper.accessor("original_text", {
        header: "Image/PDF",
        cell: info => (
          <Box maw={220} miw={160}>
            <PreviewTextButton
              text={info.getValue()}
              title="OCR Source"
              onOpen={() => {
                const suggestion = info.row.original;
                onOpenDetail({
                  title: "OCR Suggestion",
                  rows: [
                    { label: "Source", value: suggestion.original_text },
                    { label: "OCR Text", value: drafts[suggestion.id] ?? suggestion.suggested_text ?? "No OCR text" },
                    { label: "Status", value: suggestion.status },
                    { label: "Confidence", value: formatPercent(suggestion.confidence) },
                    { label: "Rationale", value: suggestion.rationale || "No rationale" },
                    { label: "Suggestion ID", value: suggestion.id },
                  ],
                });
              }}
            />
            <Badge color={statusColor(info.row.original.status)} mt={6} radius="sm" variant="dot">
              {info.row.original.status}
            </Badge>
          </Box>
        ),
      }),
      columnHelper.display({
        id: "text_on_screen",
        header: "Text on Screen",
        cell: info => {
          const suggestion = info.row.original;

          return (
            <Textarea
              aria-label={`OCR text for ${suggestion.original_text}`}
              autoComplete="off"
              autosize
              maxRows={3}
              minRows={3}
              name={`ocr-${suggestion.id}`}
              onChange={event => onDraftChange(suggestion.id, event.currentTarget.value)}
              value={drafts[suggestion.id] ?? suggestion.suggested_text ?? ""}
              w={300}
            />
          );
        },
      }),
      columnHelper.display({
        id: "suggestions",
        header: "Suggestions",
        cell: info => {
          const suggestion = info.row.original;

          return (
            <Stack gap="xs" miw={260}>
              <Badge color="grape" radius="sm" variant="light" w="fit-content">
                {formatPercent(suggestion.confidence)}
              </Badge>
              <Text c="dimmed" size="xs">
                {suggestion.rationale || "Review the extracted screen text."}
              </Text>
              <SuggestionActions suggestion={suggestion} working={working} onReview={onReview} />
            </Stack>
          );
        },
      }),
    ];
  }, [drafts, onDraftChange, onOpenDetail, onReview, working]);

  const table = useReactTable({
    columns,
    data: suggestions,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <PaperPanel title="OCR" eyebrow="Image/PDF, text on screen, suggestions">
      <Stack gap="md">
        <Group justify="space-between">
          <Box>
            <Text c="dimmed" size="sm">
              Pending rows: {pagination.total}
            </Text>
            <Text c="dimmed" size="xs">
              Latest asset import: {latestAssetImport?.filename ?? "No PDF/image import yet"}
            </Text>
          </Box>
          <Button color="green" disabled={working || !latestAssetImport} onClick={onRunOcr}>
            Run OCR
          </Button>
        </Group>
        {loading ? (
          <LoadingBlock message="Loading OCR suggestions…" />
        ) : suggestions.length === 0 ? (
          <Text c="dimmed" size="sm">
            No pending OCR suggestions.
          </Text>
        ) : (
          <ScrollArea type="auto">
            <Table miw={920} highlightOnHover>
              <Table.Thead>
                {table.getHeaderGroups().map(headerGroup => (
                  <Table.Tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <Table.Th key={header.id}>
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </Table.Th>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Thead>
              <Table.Tbody>
                {table.getRowModel().rows.map(row => (
                  <Table.Tr key={row.id}>
                    {row.getVisibleCells().map(cell => (
                      <Table.Td key={cell.id} style={{ verticalAlign: "top" }}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </Table.Td>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
        <PaginatedTableFooter pagination={pagination} pageIndex={pageIndex} onPageChange={onPageChange} />
      </Stack>
    </PaperPanel>
  );
}

function translationValue(label: Label) {
  const value = label.value["text"];
  return typeof value === "string" ? value : JSON.stringify(label.value);
}

function TranslationTable({
  labels,
  suggestions,
  drafts,
  labelsPagination,
  suggestionsPagination,
  labelsPageIndex,
  suggestionsPageIndex,
  research,
  loading,
  working,
  onGenerate,
  onOpenDetail,
  onLabelsPageChange,
  onSuggestionsPageChange,
  onDraftChange,
  onReview,
}: {
  labels: Label[];
  suggestions: Suggestion[];
  drafts: TextDraftMap;
  labelsPagination: PaginationMeta;
  suggestionsPagination: PaginationMeta;
  labelsPageIndex: number;
  suggestionsPageIndex: number;
  research: ResearchArtifact | null;
  loading: boolean;
  working: boolean;
  onGenerate: () => void;
  onOpenDetail: (detail: DetailContent) => void;
  onLabelsPageChange: (pageIndex: number) => void;
  onSuggestionsPageChange: (pageIndex: number) => void;
  onDraftChange: (id: string, value: string) => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
}) {
  const labelColumns = useMemo(() => {
    const columnHelper = createColumnHelper<Label>();

    return [
      columnHelper.accessor(row => row.data_text ?? "", {
        id: "text",
        header: "Text",
        cell: info => (
          <Box maw={260} miw={180}>
            <PreviewTextButton
              text={info.getValue()}
              title="Source Text"
              onOpen={() => {
                const label = info.row.original;
                onOpenDetail({
                  title: "Translation Label",
                  rows: [
                    { label: "Source Text", value: label.data_text ?? "No source text" },
                    { label: "Translation", value: translationValue(label) },
                    { label: "Source", value: label.source },
                    { label: "Label ID", value: label.id },
                  ],
                });
              }}
            />
          </Box>
        ),
      }),
      columnHelper.accessor(row => translationValue(row), {
        id: "translation",
        header: "Translation",
        cell: info => (
          <Box maw={280} miw={180}>
            <PreviewTextButton
              fw={500}
              text={info.getValue()}
              title="Translation"
              onOpen={() => {
                const label = info.row.original;
                onOpenDetail({
                  title: "Translation Label",
                  rows: [
                    { label: "Source Text", value: label.data_text ?? "No source text" },
                    { label: "Translation", value: translationValue(label) },
                    { label: "Source", value: label.source },
                    { label: "Label ID", value: label.id },
                  ],
                });
              }}
            />
          </Box>
        ),
      }),
      columnHelper.accessor("source", {
        header: "Source",
        cell: info => (
          <Badge color="violet" radius="sm" variant="light">
            {info.getValue()}
          </Badge>
        ),
      }),
    ];
  }, [onOpenDetail]);

  const suggestionColumns = useMemo(() => {
    const columnHelper = createColumnHelper<Suggestion>();

    return [
      columnHelper.accessor("original_text", {
        header: "Text",
        cell: info => (
          <Box maw={260} miw={180}>
            <PreviewTextButton
              text={info.getValue()}
              title="Translation Source"
              onOpen={() => {
                const suggestion = info.row.original;
                onOpenDetail({
                  title: "Translation Suggestion",
                  rows: [
                    { label: "Source Text", value: suggestion.original_text },
                    { label: "Suggested Translation", value: drafts[suggestion.id] ?? suggestion.suggested_text ?? "" },
                    { label: "Status", value: suggestion.status },
                    { label: "Confidence", value: formatPercent(suggestion.confidence) },
                    { label: "Rationale", value: suggestion.rationale || "No rationale" },
                    { label: "Suggestion ID", value: suggestion.id },
                  ],
                });
              }}
            />
            <Badge color={statusColor(info.row.original.status)} mt={6} radius="sm" variant="dot">
              {info.row.original.status}
            </Badge>
          </Box>
        ),
      }),
      columnHelper.display({
        id: "translation",
        header: "Suggested Translation",
        cell: info => {
          const suggestion = info.row.original;
          return (
            <Textarea
              aria-label={`Translation for ${suggestion.original_text}`}
              autoComplete="off"
              autosize
              maxRows={3}
              minRows={2}
              name={`translation-${suggestion.id}`}
              onChange={event => onDraftChange(suggestion.id, event.currentTarget.value)}
              value={drafts[suggestion.id] ?? suggestion.suggested_text ?? ""}
              w={320}
            />
          );
        },
      }),
      columnHelper.display({
        id: "actions",
        header: "Review",
        cell: info => {
          const suggestion = info.row.original;
          return (
            <Stack gap="xs" miw={240}>
              <Group gap="xs">
                <Badge color="grape" radius="sm" variant="light">
                  {formatPercent(suggestion.confidence)}
                </Badge>
                <Text c="dimmed" size="xs">
                  AI suggestion
                </Text>
              </Group>
              <Text c="dimmed" size="xs">
                {suggestion.rationale || "Review the suggested translation."}
              </Text>
              <SuggestionActions suggestion={suggestion} working={working} onReview={onReview} />
            </Stack>
          );
        },
      }),
    ];
  }, [drafts, onDraftChange, onOpenDetail, onReview, working]);

  const labelTable = useReactTable({
    columns: labelColumns,
    data: labels,
    getCoreRowModel: getCoreRowModel(),
  });

  const suggestionTable = useReactTable({
    columns: suggestionColumns,
    data: suggestions,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <PaperPanel title="Translate" eyebrow="Labels, research, suggestions">
      <Stack gap="md">
        <Group justify="space-between" wrap="wrap">
          <Text c="dimmed" size="sm">
            Pending suggestions: {suggestionsPagination.total}
          </Text>
          <Button disabled={working || !research} onClick={onGenerate}>
            Generate 5 Suggestions
          </Button>
        </Group>
        {!research ? (
          <Text c="dimmed" size="sm">
            Run translation research before generating translation suggestions.
          </Text>
        ) : null}
        {loading ? (
          <LoadingBlock message="Loading translations…" />
        ) : suggestions.length > 0 ? (
          <ScrollArea type="auto">
            <Table miw={940} highlightOnHover>
              <Table.Thead>
                {suggestionTable.getHeaderGroups().map(headerGroup => (
                  <Table.Tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <Table.Th key={header.id}>
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </Table.Th>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Thead>
              <Table.Tbody>
                {suggestionTable.getRowModel().rows.map(row => (
                  <Table.Tr key={row.id}>
                    {row.getVisibleCells().map(cell => (
                      <Table.Td key={cell.id} style={{ verticalAlign: "top" }}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </Table.Td>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        ) : (
          <Text c="dimmed" size="sm">
            No pending translation suggestions.
          </Text>
        )}
        <PaginatedTableFooter
          pagination={suggestionsPagination}
          pageIndex={suggestionsPageIndex}
          onPageChange={onSuggestionsPageChange}
        />
        <Divider />
        <Text fw={700} size="sm">
          Saved translation labels: {labelsPagination.total}
        </Text>
        {labels.length === 0 ? (
          <Text c="dimmed" size="sm">
            No translation labels yet. Import a translation CSV or accept AI suggestions.
          </Text>
        ) : (
          <ScrollArea type="auto">
            <Table miw={780} highlightOnHover>
              <Table.Thead>
                {labelTable.getHeaderGroups().map(headerGroup => (
                  <Table.Tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <Table.Th key={header.id}>
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </Table.Th>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Thead>
              <Table.Tbody>
                {labelTable.getRowModel().rows.map(row => (
                  <Table.Tr key={row.id}>
                    {row.getVisibleCells().map(cell => (
                      <Table.Td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</Table.Td>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
        <PaginatedTableFooter
          pagination={labelsPagination}
          pageIndex={labelsPageIndex}
          onPageChange={onLabelsPageChange}
        />
      </Stack>
    </PaperPanel>
  );
}

function ModelsPanel({
  acceptedPosCount,
  posModel,
  working,
  onTrainPos,
}: {
  acceptedPosCount: number;
  posModel: PosModel | null;
  working: boolean;
  onTrainPos: () => void;
}) {
  const minimumExamples = posModel?.minimum_examples ?? 20;
  const minimumMet = posModel?.minimum_examples_met ?? acceptedPosCount >= minimumExamples;
  const trainingMode = posModel?.mode ?? "demo";
  const posStatus = posModel
    ? `${trainingMode === "demo" ? "demo " : ""}${posModel.status.replaceAll("_", " ")}`
    : "not started";
  const posDescription = minimumMet
    ? `${acceptedPosCount} reviewed examples are ready for the tagger.`
    : `${acceptedPosCount}/${minimumExamples} reviewed examples; demo mode can still run for the presentation.`;

  return (
    <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
      <ModelTrainingCard
        actionLabel="Train OCR Model"
        description="Tune OCR extraction for PDFs and image scans in this language workspace."
        disabled
        status="Needs document examples"
        title="OCR"
        tone="grape"
      />
      <ModelTrainingCard
        actionLabel="Train Translation Model"
        description="Train a translation model from aligned text, corrections, and reviewer suggestions."
        disabled
        status="Dataset alignment needed"
        title="Translation"
        tone="violet"
      />
      <ModelTrainingCard
        actionLabel="Run Demo POS Training"
        description={posDescription}
        disabled={working}
        onAction={onTrainPos}
        status={posStatus}
        title="POS Tagging"
        tone="green"
      />
    </SimpleGrid>
  );
}

function ModelTrainingCard({
  actionLabel,
  description,
  disabled,
  onAction,
  status,
  title,
  tone,
}: {
  actionLabel: string;
  description: string;
  disabled?: boolean;
  onAction?: () => void;
  status: string;
  title: string;
  tone: string;
}) {
  return (
    <Card withBorder radius="md" p="lg" style={{ background: UI.panel, borderColor: UI.border }}>
      <Stack gap="md" h="100%">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Box>
            <Text c="dimmed" fw={700} size="xs" tt="uppercase">
              Model
            </Text>
            <Title order={3} size="h3">
              {title}
            </Title>
          </Box>
          <ThemeIcon color={tone} radius="md" variant="light">
            {title.slice(0, 2)}
          </ThemeIcon>
        </Group>
        <Text c="dimmed" size="sm">
          {description}
        </Text>
        <Badge color={tone} radius="sm" variant="light" w="fit-content">
          {status}
        </Badge>
        <Button color={tone} disabled={disabled} mt="auto" onClick={onAction} variant="light">
          {actionLabel}
        </Button>
      </Stack>
    </Card>
  );
}

function jobWarnings(job: Job): ProviderWarning[] {
  const warnings = job.metadata["warnings"];
  if (!Array.isArray(warnings)) return [];
  return warnings.filter(
    (warning): warning is ProviderWarning =>
      typeof warning === "object" &&
      warning !== null &&
      "provider" in warning &&
      "stage" in warning &&
      "message" in warning,
  );
}

function JobsPanel({ jobs }: { jobs: Job[] }) {
  const visibleJobs = jobs.slice(0, 3);
  return (
    <CompactPanel title="Recent Jobs" eyebrow="Last 3 runs">
      {visibleJobs.length === 0 ? (
        <Text c="dimmed" size="sm">
          No recent jobs.
        </Text>
      ) : (
        <Stack gap="xs">
          {visibleJobs.map((job, index) => {
          const warnings = jobWarnings(job);
          const usedFallback = job.metadata["used_fallback"] === true || warnings.length > 0;

          return (
            <Box key={job.id}>
              {index > 0 ? <Divider mb="xs" /> : null}
              <Stack gap={4}>
                <Group justify="space-between" wrap="nowrap">
                  <Box miw={0}>
                    <Text fw={700} size="sm" truncate="end">
                      {job.type}
                    </Text>
                    <Text c="dimmed" size="xs" truncate="end">
                      {job.message || job.id}
                    </Text>
                  </Box>
                  <Badge color={statusColor(job.status)} radius="sm" variant="dot" style={{ flexShrink: 0 }}>
                    {job.status}
                  </Badge>
                </Group>
                {usedFallback ? (
                  <Badge color="yellow" radius="sm" variant="light" w="fit-content">
                    Demo fallback
                  </Badge>
                ) : null}
                {warnings.slice(0, 1).map(warning => (
                  <Text key={`${job.id}-${warning.provider}-${warning.stage}`} c="dimmed" size="xs">
                    {warning.provider}: {warning.message}
                  </Text>
                ))}
              </Stack>
            </Box>
          );
        })}
        </Stack>
      )}
    </CompactPanel>
  );
}

export default App;
