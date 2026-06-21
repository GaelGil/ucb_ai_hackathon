import {
  ActionIcon,
  AppShell,
  Badge,
  Box,
  Button,
  Card,
  Divider,
  FileInput,
  Group,
  Loader,
  Modal,
  Paper,
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

const API_BASE_URL = "http://127.0.0.1:8000";

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
type SuggestionType = "pos" | "ocr" | "translation" | "emotion" | "intention" | "text" | "custom";
type SuggestionStatus = "pending" | "accepted" | "denied" | "updated" | "approved" | "edited";
type LabelSource = "csv_import" | "human" | "ai_accepted" | "ai_updated";

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
  status: string;
  created_at: string;
};

type ResearchArtifact = {
  id: string;
  summary: string;
  guidelines: string[];
  sources: { title: string; url: string; excerpt: string }[];
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

type PosModel = {
  status: string;
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
};

type Toast = {
  tone: "violet" | "red" | "green";
  message: string;
};

type DraftMap = Record<string, TokenSuggestion[]>;
type TextDraftMap = Record<string, string>;
type WorkspaceTab = "pos" | "ocr" | "translate" | "upload" | "models";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: options?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
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

export function App() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [ocrSuggestions, setOcrSuggestions] = useState<Suggestion[]>([]);
  const [translationLabels, setTranslationLabels] = useState<Label[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [working, setWorking] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("pos");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [addLanguageFormOpen, setAddLanguageFormOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Dataset | null>(null);

  const [datasetName, setDatasetName] = useState("");
  const [languageCode, setLanguageCode] = useState("");
  const [languageName, setLanguageName] = useState("");
  const [manualText, setManualText] = useState("");
  const [manualSource, setManualSource] = useState<SourceType>("text");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [tokenDrafts, setTokenDrafts] = useState<DraftMap>({});
  const [ocrDrafts, setOcrDrafts] = useState<TextDraftMap>({});

  const selectedDataset = useMemo(
    () => datasets.find(dataset => dataset.id === selectedDatasetId) ?? datasets[0] ?? null,
    [datasets, selectedDatasetId],
  );

  const latestAssetImport = useMemo(
    () => dashboard?.imports.find(item => item.source_type === "pdf" || item.source_type === "image") ?? null,
    [dashboard?.imports],
  );

  const pendingPosCount = dashboard?.suggestion_counts["pos:pending"] ?? 0;
  const acceptedPosCount =
    (dashboard?.suggestion_counts["pos:accepted"] ?? 0) +
    (dashboard?.suggestion_counts["pos:updated"] ?? 0) +
    (dashboard?.suggestion_counts["pos:approved"] ?? 0) +
    (dashboard?.suggestion_counts["pos:edited"] ?? 0);
  const pendingOcrCount = dashboard?.suggestion_counts["ocr:pending"] ?? 0;

  useEffect(() => {
    void loadDatasets();
  }, []);

  useEffect(() => {
    if (selectedDatasetId) {
      void refreshWorkspace(selectedDatasetId);
    } else {
      clearWorkspaceState();
    }
  }, [selectedDatasetId]);

  async function loadDatasets() {
    setDatasetsLoading(true);
    try {
      const rows = await api<Dataset[]>("/datasets");
      setDatasets(rows);
      setSelectedDatasetId(current =>
        rows.some(dataset => dataset.id === current) ? current : rows[0]?.id || "",
      );
    } catch (error) {
      showError(error);
    } finally {
      setDatasetsLoading(false);
    }
  }

  async function refreshWorkspace(datasetId = selectedDatasetId) {
    if (!datasetId) return;
    setWorkspaceLoading(true);
    try {
      const [nextDashboard, nextSuggestions, nextOcrSuggestions, nextTranslationLabels] = await Promise.all([
        api<Dashboard>(`/datasets/${datasetId}/dashboard`),
        api<{ suggestions: Suggestion[] }>(`/datasets/${datasetId}/suggestions?type=pos&status=pending&limit=5`),
        api<{ suggestions: Suggestion[] }>(`/datasets/${datasetId}/suggestions?type=ocr&status=pending&limit=5`),
        api<{ labels: Label[] }>(`/datasets/${datasetId}/labels?type=translation&limit=500`),
      ]);
      setDashboard(nextDashboard);
      setSuggestions(nextSuggestions.suggestions);
      setOcrSuggestions(nextOcrSuggestions.suggestions);
      setTranslationLabels(nextTranslationLabels.labels);
      setTokenDrafts(previous => {
        const next = { ...previous };
        for (const suggestion of nextSuggestions.suggestions) {
          next[suggestion.id] ??= suggestion.tokens;
        }
        return next;
      });
      setOcrDrafts(previous => {
        const next = { ...previous };
        for (const suggestion of nextOcrSuggestions.suggestions) {
          next[suggestion.id] ??= suggestion.suggested_text ?? "";
        }
        return next;
      });
    } catch (error) {
      showError(error);
    } finally {
      setWorkspaceLoading(false);
    }
  }

  async function runAction<T>(callback: () => Promise<T>, successMessage: string) {
    setWorking(true);
    try {
      const result = await callback();
      setToast({ tone: "green", message: successMessage });
      await refreshWorkspace();
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
    const created = await runAction(
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
    );
    if (created) {
      const rows = await api<Dataset[]>("/datasets");
      setDatasets(rows);
      setSelectedDatasetId(created.id);
      setAddLanguageFormOpen(false);
    }
  }

  async function deleteDataset(dataset: Dataset) {
    setWorking(true);
    try {
      await api<void>(`/datasets/${dataset.id}`, { method: "DELETE" });
      const rows = await api<Dataset[]>("/datasets");
      const currentStillExists = rows.some(item => item.id === selectedDatasetId);
      const nextSelectedId = currentStillExists ? selectedDatasetId : rows[0]?.id || "";

      setDatasets(rows);
      setSelectedDatasetId(nextSelectedId);
      setDeleteTarget(null);
      setToast({ tone: "green", message: "Language deleted" });
      setJobs([]);

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
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/imports`, {
        method: "POST",
        body: JSON.stringify({ text: manualText, source_type: manualSource }),
      });
      rememberJob(response.job);
      return response;
    }, "Text imported");
  }

  async function importFile() {
    if (!selectedDatasetId || !uploadFile) return;
    const form = new FormData();
    form.append("file", uploadFile);
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/imports`, {
        method: "POST",
        body: form,
      });
      rememberJob(response.job);
      setUploadFile(null);
      return response;
    }, "File imported");
  }

  async function runResearch(force = false) {
    if (!selectedDatasetId) return;
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/research?force=${force}`, {
        method: "POST",
      });
      rememberJob(response.job);
      return response;
    }, force ? "Research refreshed" : "Research ready");
  }

  async function generatePosSuggestions() {
    if (!selectedDatasetId) return;
    await runAction(async () => {
      const response = await api<{ job: Job }>(`/datasets/${selectedDatasetId}/pos-suggestions`, {
        method: "POST",
        body: JSON.stringify({ limit: 5 }),
      });
      rememberJob(response.job);
      return response;
    }, "Generated POS suggestions");
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
    }, "OCR suggestions generated");
  }

  async function reviewSuggestion(suggestion: Suggestion, action: SuggestionStatus) {
    await runAction(async () => {
      const payload =
        action === "updated" && suggestion.type === "pos"
          ? { action, edited_tokens: tokenDrafts[suggestion.id] ?? suggestion.tokens }
          : action === "updated"
            ? { action, edited_text: ocrDrafts[suggestion.id] ?? suggestion.suggested_text ?? "" }
              : { action };
      return api<Suggestion>(`/suggestions/${suggestion.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    }, action === "accepted" ? "Suggestion accepted" : action === "denied" ? "Suggestion denied" : "Suggestion updated");
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
    }, "POS model trigger completed");
  }

  function rememberJob(job: Job) {
    setJobs(previous => [job, ...previous.filter(item => item.id !== job.id)].slice(0, 5));
  }

  function clearWorkspaceState() {
    setDashboard(null);
    setSuggestions([]);
    setOcrSuggestions([]);
    setTranslationLabels([]);
    setTokenDrafts({});
    setOcrDrafts({});
    setJobs([]);
    setWorkspaceLoading(false);
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
                  loading={workspaceLoading}
                  working={working}
                  onGenerate={() => void generatePosSuggestions()}
                  onReview={(suggestion, action) => void reviewSuggestion(suggestion, action)}
                  onTokenChange={updateTokenDraft}
                />
              </Tabs.Panel>

              <Tabs.Panel value="ocr" pt="md">
                <OcrSuggestionsTable
                  latestAssetImport={latestAssetImport}
                  suggestions={ocrSuggestions}
                  drafts={ocrDrafts}
                  loading={workspaceLoading}
                  working={working}
                  onRunOcr={() => void runOcr()}
                  onDraftChange={(id, value) => setOcrDrafts(previous => ({ ...previous, [id]: value }))}
                  onReview={(suggestion, action) => void reviewSuggestion(suggestion, action)}
                />
              </Tabs.Panel>

              <Tabs.Panel value="translate" pt="md">
                <TranslationTable labels={translationLabels} loading={workspaceLoading} />
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
                        Import Sentences
                      </Button>
                    </Stack>
                  </PaperPanel>

                  <PaperPanel title="Files and Imports" eyebrow="CSV, TXT, PDF, image">
                    <Stack gap="md">
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
                          disabled={working || !uploadFile}
                          leftSection={<TbUpload aria-hidden="true" size={16} />}
                          onClick={() => void importFile()}
                        >
                          Upload
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

function ResearchPanel({
  dashboard,
  working,
  onResearch,
  onRefreshResearch,
}: {
  dashboard: Dashboard | null;
  working: boolean;
  onResearch: () => void;
  onRefreshResearch: () => void;
}) {
  const research = dashboard?.research;
  return (
    <PaperPanel title="Cached research notes" eyebrow="Dataset + language">
      <Stack gap="sm">
        <Group gap="xs">
          <Button disabled={working} onClick={onResearch}>
            {research ? "Use Cached Research" : "Run Research"}
          </Button>
          <Button color="green" disabled={working} onClick={onRefreshResearch} variant="light">
            Refresh
          </Button>
        </Group>
        {research ? (
          <>
            <Text size="sm">{research.summary}</Text>
            <Stack gap={6}>
              {research.guidelines.map(guideline => (
                <Text key={guideline} c="dimmed" size="sm">
                  {guideline}
                </Text>
              ))}
            </Stack>
            <Group gap="xs">
              {research.sources.map(source => (
                <Badge key={source.url} color="violet" radius="sm" variant="outline">
                  {source.title}
                </Badge>
              ))}
            </Group>
          </>
        ) : (
          <Text c="dimmed" size="sm">
            Research has not been generated for this workspace yet.
          </Text>
        )}
      </Stack>
    </PaperPanel>
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

function PosSuggestionsTable({
  suggestions,
  tokenDrafts,
  loading,
  working,
  onGenerate,
  onReview,
  onTokenChange,
}: {
  suggestions: Suggestion[];
  tokenDrafts: DraftMap;
  loading: boolean;
  working: boolean;
  onGenerate: () => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
  onTokenChange: (suggestionId: string, tokenIndex: number, tag: string | null) => void;
}) {
  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<Suggestion>();

    return [
      columnHelper.accessor("original_text", {
        header: "Text",
        cell: info => (
          <Box maw={360}>
            <Text fw={700} size="sm">
              {info.getValue()}
            </Text>
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
            <Stack gap={6} miw={260}>
              {tokens.map(token => (
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
  }, [onReview, onTokenChange, tokenDrafts, working]);

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
            Pending rows: {suggestions.length}
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
  loading,
  working,
  onRunOcr,
  onDraftChange,
  onReview,
}: {
  latestAssetImport: ImportRecord | null;
  suggestions: Suggestion[];
  drafts: TextDraftMap;
  loading: boolean;
  working: boolean;
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
          <Box maw={260}>
            <Text fw={700} size="sm" truncate="end">
              {info.getValue()}
            </Text>
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
              minRows={3}
              name={`ocr-${suggestion.id}`}
              onChange={event => onDraftChange(suggestion.id, event.currentTarget.value)}
              value={drafts[suggestion.id] ?? suggestion.suggested_text ?? ""}
              w={320}
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
  }, [drafts, onDraftChange, onReview, working]);

  const table = useReactTable({
    columns,
    data: suggestions,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <PaperPanel title="OCR" eyebrow="Image/PDF, text on screen, suggestions">
      <Stack gap="md">
        <Group justify="space-between">
          <Text c="dimmed" size="sm">
            Latest asset import: {latestAssetImport?.filename ?? "No PDF/image import yet"}
          </Text>
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
      </Stack>
    </PaperPanel>
  );
}

function translationValue(label: Label) {
  const value = label.value["text"];
  return typeof value === "string" ? value : JSON.stringify(label.value);
}

function TranslationTable({ labels, loading }: { labels: Label[]; loading: boolean }) {
  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<Label>();

    return [
      columnHelper.accessor(row => row.data_text ?? "", {
        id: "text",
        header: "Text",
        cell: info => (
          <Text fw={700} size="sm">
            {info.getValue() || "No source text"}
          </Text>
        ),
      }),
      columnHelper.accessor(row => translationValue(row), {
        id: "translation",
        header: "Translation",
        cell: info => (
          <Text size="sm">
            {info.getValue()}
          </Text>
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
  }, []);

  const table = useReactTable({
    columns,
    data: labels,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <PaperPanel title="Translate" eyebrow="Backend translation labels">
      {loading ? (
        <LoadingBlock message="Loading translations…" />
      ) : labels.length === 0 ? (
        <Text c="dimmed" size="sm">
          No translation labels yet. Import a CSV with a translation column to populate this table.
        </Text>
      ) : (
      <ScrollArea type="auto">
        <Table miw={780} highlightOnHover>
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
      )}
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
        actionLabel="Train POS Tagger"
        description={`${acceptedPosCount} accepted examples are ready to train the tagger.`}
        disabled={working}
        onAction={onTrainPos}
        status={posModel?.status.replaceAll("_", " ") ?? "not started"}
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

function JobsPanel({ jobs }: { jobs: Job[] }) {
  if (jobs.length === 0) return null;
  return (
    <PaperPanel title="Recent jobs" eyebrow="Polling-compatible status">
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="sm">
        {jobs.map(job => (
          <Card key={job.id} withBorder radius="md" p="sm" style={{ background: UI.panelSoft, borderColor: UI.border }}>
            <Group justify="space-between" wrap="nowrap">
              <Box>
                <Text fw={700} size="sm">
                  {job.type}
                </Text>
                <Text c="dimmed" size="xs">
                  {job.message || job.id}
                </Text>
              </Box>
              <Badge color={statusColor(job.status)} radius="sm" variant="dot">
                {job.status}
              </Badge>
            </Group>
          </Card>
        ))}
      </SimpleGrid>
    </PaperPanel>
  );
}

export default App;
