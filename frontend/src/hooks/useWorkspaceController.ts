import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { EMPTY_DATASETS } from "@/lib/constants";
import {
  assertJobSucceeded,
  importSuccessMessage,
  isJobActive,
  lastPageIndex,
} from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import type {
  Dataset,
  DetailContent,
  DraftMap,
  ImportKind,
  Job,
  ResearchType,
  SourceType,
  Suggestion,
  SuggestionStatus,
  SuggestionType,
  TextDraftMap,
  Toast,
  WorkspaceTab,
} from "@/types/domain";

import { useDatasets, useWorkspaceData } from "./useWorkspaceData";

export function useWorkspaceController() {
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
  const [selectedOcrImportIds, setSelectedOcrImportIds] = useState<string[]>([]);
  const [translationDrafts, setTranslationDrafts] = useState<TextDraftMap>({});

  const selectedDataset = useMemo(
    () => datasets.find(dataset => dataset.id === selectedDatasetId) ?? datasets[0] ?? null,
    [datasets, selectedDatasetId],
  );

  const imageAssetImports = useMemo(
    () => dashboard?.imports.filter(item => item.source_type === "image") ?? [],
    [dashboard?.imports],
  );
  const latestAssetImport = imageAssetImports[0] ?? null;

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
          await invalidateResearch("pos", selectedDatasetId);
          await invalidateResearch("translation", selectedDatasetId);
          await invalidateSuggestions("pos", selectedDatasetId);
          await invalidateSuggestions("ocr", selectedDatasetId);
          await invalidateSuggestions("translation", selectedDatasetId);
          await invalidateTranslationLabels(selectedDatasetId);
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
    setSelectedOcrImportIds(current => {
      const available = new Set(imageAssetImports.map(item => item.id));
      const kept = current.filter(id => available.has(id));
      if (kept.length > 0) return kept;
      return imageAssetImports[0] ? [imageAssetImports[0].id] : [];
    });
  }, [imageAssetImports]);

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
    if (!selectedDatasetId || selectedOcrImportIds.length === 0) return;
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/ocr`, {
        method: "POST",
        body: JSON.stringify({ import_ids: selectedOcrImportIds }),
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

  return {
    acceptedPosCount,
    activeResearchType,
    activeTab,
    addLanguageFormOpen,
    createDataset,
    dashboard,
    datasetName,
    datasets,
    datasetsLoading,
    deleteDataset,
    deleteTarget,
    fileImportKind,
    generatePosSuggestions,
    generateTranslationSuggestions,
    handleTabChange,
    importFile,
    importManualText,
    imageAssetImports,
    languageCode,
    languageName,
    latestAssetImport,
    manualImportKind,
    manualSource,
    manualText,
    ocrDrafts,
    ocrSuggestions,
    ocrSuggestionsPage,
    openDetail,
    posSuggestionsPage,
    researchByType,
    reviewSuggestion,
    runOcr,
    runResearch,
    selectedDataset,
    selectedDetail,
    selectedOcrImportIds,
    setAddLanguageFormOpen,
    setDatasetName,
    setDeleteTarget,
    setFileImportKind,
    setLanguageCode,
    setLanguageName,
    setManualImportKind,
    setManualSource,
    setManualText,
    setOcrDrafts,
    setOcrSuggestionsPage,
    setPosSuggestionsPage,
    setSelectedOcrImportIds,
    setSelectedDatasetId,
    setSelectedDetail,
    setSidebarCollapsed,
    setToast,
    setTranslationDrafts,
    setTranslationLabelsPage,
    setTranslationSuggestionsPage,
    setUploadFile,
    sidebarCollapsed,
    suggestions,
    toast,
    tokenDrafts,
    trainPosModel,
    translationDrafts,
    translationLabels,
    translationLabelsPage,
    translationSuggestions,
    translationSuggestionsPage,
    updateTokenDraft,
    uploadFile,
    uploadFileIsCsv,
    working,
    workspaceData,
    workspaceLoading,
    jobs,
    setActiveResearchType,
  };
}
