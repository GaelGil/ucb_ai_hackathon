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
  NavLink,
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
  TbLayoutSidebarLeftExpand,
  TbPlus,
  TbTags,
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
type SuggestionType = "pos" | "ocr";
type SuggestionStatus = "pending" | "approved" | "denied" | "edited";

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
type WorkspaceTab = "all" | "pos" | "ocr" | "upload";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: options?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
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
    case "approved":
    case "ready":
    case "succeeded":
      return "green";
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
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("all");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [datasetName, setDatasetName] = useState("Nahuatl field notes");
  const [languageCode, setLanguageCode] = useState("nah");
  const [languageName, setLanguageName] = useState("Nahuatl");
  const [manualText, setManualText] = useState("muchas flores son blancas\nel agua corre rapido");
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
    (dashboard?.suggestion_counts["pos:approved"] ?? 0) + (dashboard?.suggestion_counts["pos:edited"] ?? 0);
  const pendingOcrCount = dashboard?.suggestion_counts["ocr:pending"] ?? 0;

  useEffect(() => {
    void loadDatasets();
  }, []);

  useEffect(() => {
    if (selectedDatasetId) {
      void refreshWorkspace(selectedDatasetId);
    }
  }, [selectedDatasetId]);

  async function loadDatasets() {
    setLoading(true);
    try {
      const rows = await api<Dataset[]>("/datasets");
      setDatasets(rows);
      setSelectedDatasetId(current => current || rows[0]?.id || "");
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function refreshWorkspace(datasetId = selectedDatasetId) {
    if (!datasetId) return;
    try {
      const [nextDashboard, nextSuggestions, nextOcrSuggestions] = await Promise.all([
        api<Dashboard>(`/datasets/${datasetId}/dashboard`),
        api<{ suggestions: Suggestion[] }>(`/datasets/${datasetId}/suggestions?type=pos&status=pending&limit=5`),
        api<{ suggestions: Suggestion[] }>(`/datasets/${datasetId}/suggestions?type=ocr&status=pending&limit=5`),
      ]);
      setDashboard(nextDashboard);
      setSuggestions(nextSuggestions.suggestions);
      setOcrSuggestions(nextOcrSuggestions.suggestions);
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
        action === "edited" && suggestion.type === "pos"
          ? { action, edited_tokens: tokenDrafts[suggestion.id] ?? suggestion.tokens }
          : action === "edited"
            ? { action, edited_text: ocrDrafts[suggestion.id] ?? suggestion.suggested_text ?? "" }
            : { action };
      return api<Suggestion>(`/suggestions/${suggestion.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    }, action === "approved" ? "Suggestion approved" : action === "denied" ? "Suggestion denied" : "Suggestion edited");
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
    if (value === "all" || value === "pos" || value === "ocr" || value === "upload") {
      setActiveTab(value);
    }
  }

  if (loading) {
    return (
      <Box bg={UI.background} mih="100vh" p="xl">
        <Group justify="center" mt="20vh">
          <Loader color="violet" />
          <Text c="dimmed">Loading workspace…</Text>
        </Group>
      </Box>
    );
  }

  return (
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
          <Title order={1} size="h3" lh={1.1} truncate>
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
              <ThemeIcon color="violet" radius="md" size={42} variant="filled">
                LB
              </ThemeIcon>
              <Tooltip label="Expand Sidebar" position="right">
                <ActionIcon
                  aria-label="Expand sidebar"
                  color="gray"
                  onClick={() => setSidebarCollapsed(false)}
                  size={38}
                  variant="subtle"
                >
                  <TbLayoutSidebarLeftExpand aria-hidden="true" size={20} />
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
                  <Text fw={850} lh={1} size="lg" truncate>
                    LangBase
                  </Text>
                  <Text c="dimmed" size="xs" truncate>
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
              {datasets.length === 0 ? (
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
                    <NavLink
                      key={dataset.id}
                      active={dataset.id === selectedDataset?.id}
                      description={`${dataset.language_name} · ${dataset.language_code}`}
                      label={dataset.name}
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
                      variant="filled"
                    />
                  ),
                )
              )}
            </Stack>
          </ScrollArea>

          <Divider />
          {sidebarCollapsed ? (
            <Tooltip label="Expand Sidebar to Add Language" position="right">
              <ActionIcon
                aria-label="Expand sidebar to add a language"
                color="green"
                onClick={() => setSidebarCollapsed(false)}
                radius="md"
                size={46}
                variant="light"
              >
                <TbPlus aria-hidden="true" size={20} />
              </ActionIcon>
            </Tooltip>
          ) : (
            <Box
              component="form"
              onSubmit={event => {
                event.preventDefault();
                void createDataset();
              }}
            >
              <Stack gap="xs">
                <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                  New Language
                </Text>
                <TextInput
                  autoComplete="off"
                  label="Dataset"
                  name="datasetName"
                  onChange={event => setDatasetName(event.currentTarget.value)}
                  placeholder="Nahuatl field notes…"
                  size="xs"
                  value={datasetName}
                />
                <Group grow>
                  <TextInput
                    autoComplete="off"
                    label="Code"
                    name="languageCode"
                    onChange={event => setLanguageCode(event.currentTarget.value)}
                    placeholder="nah…"
                    size="xs"
                    spellCheck={false}
                    value={languageCode}
                  />
                  <TextInput
                    autoComplete="off"
                    label="Language"
                    name="languageName"
                    onChange={event => setLanguageName(event.currentTarget.value)}
                    placeholder="Nahuatl…"
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
          )}
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

            <Tabs value={activeTab} onChange={handleTabChange} radius="md" variant="pills">
              <Tabs.List>
                <Tabs.Tab leftSection={<TbDatabase aria-hidden="true" size={16} />} value="all">
                  All
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbTags aria-hidden="true" size={16} />} value="pos">
                  POS
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbWand aria-hidden="true" size={16} />} value="ocr">
                  OCR
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbUpload aria-hidden="true" size={16} />} value="upload">
                  Upload
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="all" pt="md">
                <Stack gap="md">
                  <SimpleGrid cols={{ base: 1, md: 4 }} spacing="md">
                    <MetricCard label="Research" value={dashboard?.research ? "Cached" : "Not Run"} tone="violet" />
                    <MetricCard label="Imports" value={`${dashboard?.imports.length ?? 0}`} tone="green" />
                    <MetricCard label="OCR Review" value={`${pendingOcrCount} Pending`} tone="grape" />
                    <MetricCard label="POS Model" value={dashboard?.pos_model.model_name ?? "Demo Trigger"} tone="lime" />
                  </SimpleGrid>
                  <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
                    <PaperPanel title="Imports" eyebrow="Dataset sources">
                      <ImportsTable imports={dashboard?.imports ?? []} />
                    </PaperPanel>
                    <PaperPanel title="Workspace Status" eyebrow="All activity">
                      <Stack gap="sm">
                        <Group gap="xs">
                          <Badge color="violet" radius="sm" variant="light">
                            {dashboard?.item_count ?? 0} text items
                          </Badge>
                          <Badge color="yellow" radius="sm" variant="light">
                            {pendingPosCount} POS pending
                          </Badge>
                          <Badge color="grape" radius="sm" variant="light">
                            {pendingOcrCount} OCR pending
                          </Badge>
                          <Badge color="green" radius="sm" variant="light">
                            {acceptedPosCount} accepted
                          </Badge>
                        </Group>
                        <Text c="dimmed" size="sm">
                          Research is {dashboard?.research ? "cached" : "not cached"} and the POS model is{" "}
                          {dashboard?.pos_model.status.replaceAll("_", " ") ?? "not started"}.
                        </Text>
                      </Stack>
                    </PaperPanel>
                  </SimpleGrid>
                  <JobsPanel jobs={jobs} />
                </Stack>
              </Tabs.Panel>

              <Tabs.Panel value="pos" pt="md">
                <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
                  <ResearchPanel
                    dashboard={dashboard}
                    working={working}
                    onResearch={() => void runResearch(false)}
                    onRefreshResearch={() => void runResearch(true)}
                  />
                  <PosBatchPanel
                    suggestions={suggestions}
                    tokenDrafts={tokenDrafts}
                    working={working}
                    onGenerate={() => void generatePosSuggestions()}
                    onReview={(suggestion, action) => void reviewSuggestion(suggestion, action)}
                    onTokenChange={updateTokenDraft}
                  />
                  <PaperPanel title="Dataset POS Tagger" eyebrow="Training trigger">
                    <Stack gap="sm">
                      <Group gap="xs">
                        <Badge color="green" radius="sm" variant="light">
                          {acceptedPosCount} accepted examples
                        </Badge>
                        <Badge color={statusColor(dashboard?.pos_model.status ?? "")} radius="sm" variant="dot">
                          {dashboard?.pos_model.status.replaceAll("_", " ") ?? "not started"}
                        </Badge>
                      </Group>
                      <Text c="dimmed" size="sm">
                        The demo trigger allows model creation before the production threshold is reached. Accepted
                        reviewer examples remain the training signal.
                      </Text>
                      <Button color="green" disabled={working} onClick={() => void trainPosModel()}>
                        Trigger POS Training
                      </Button>
                      {dashboard?.pos_model.model_name ? (
                        <Text size="sm">Model: {dashboard.pos_model.model_name}</Text>
                      ) : null}
                    </Stack>
                  </PaperPanel>
                </SimpleGrid>
              </Tabs.Panel>

              <Tabs.Panel value="ocr" pt="md">
                <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
                  <PaperPanel title="OCR Queue" eyebrow="PDF and image extraction">
                    <Stack gap="sm">
                      <Text c="dimmed" size="sm">
                        Latest asset import: {latestAssetImport?.filename ?? "No PDF/image import yet"}
                      </Text>
                      <Button color="green" disabled={working || !latestAssetImport} onClick={() => void runOcr()}>
                        Run OCR
                      </Button>
                    </Stack>
                  </PaperPanel>
                  <OcrReviewPanel
                    suggestions={ocrSuggestions}
                    drafts={ocrDrafts}
                    working={working}
                    onDraftChange={(id, value) => setOcrDrafts(previous => ({ ...previous, [id]: value }))}
                    onReview={(suggestion, action) => void reviewSuggestion(suggestion, action)}
                  />
                </SimpleGrid>
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
                      <ImportsTable imports={dashboard?.imports ?? []} />
                    </Stack>
                  </PaperPanel>
                </SimpleGrid>
              </Tabs.Panel>
            </Tabs>
          </Stack>
        </Box>
      </AppShell.Main>
    </AppShell>
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

function PosBatchPanel({
  suggestions,
  tokenDrafts,
  working,
  onGenerate,
  onReview,
  onTokenChange,
}: {
  suggestions: Suggestion[];
  tokenDrafts: DraftMap;
  working: boolean;
  onGenerate: () => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
  onTokenChange: (suggestionId: string, tokenIndex: number, tag: string | null) => void;
}) {
  return (
    <PaperPanel title="Five-at-a-time review" eyebrow="UPOS suggestions">
      <Stack gap="md">
        <Group justify="space-between">
          <Text c="dimmed" size="sm">
            Pending batch size: {suggestions.length}
          </Text>
          <Button disabled={working} onClick={onGenerate}>
            Generate 5 Suggestions
          </Button>
        </Group>
        {suggestions.length === 0 ? (
          <Text c="dimmed" size="sm">
            No pending POS suggestions. Generate a batch after uploading text.
          </Text>
        ) : (
          suggestions.map(suggestion => (
            <Card
              key={suggestion.id}
              withBorder
              radius="md"
              p="md"
              style={{ background: UI.panelSoft, borderColor: UI.border }}
            >
              <Stack gap="sm">
                <Group justify="space-between" align="flex-start">
                  <Box>
                    <Text fw={750}>{suggestion.original_text}</Text>
                    <Text c="dimmed" size="xs">
                      Confidence {formatPercent(suggestion.confidence)}
                    </Text>
                  </Box>
                  <Badge color={statusColor(suggestion.status)} radius="sm" variant="dot">
                    {suggestion.status}
                  </Badge>
                </Group>
                <Table miw={520} withTableBorder={false}>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Token</Table.Th>
                      <Table.Th>UPOS</Table.Th>
                      <Table.Th>Reason</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {(tokenDrafts[suggestion.id] ?? suggestion.tokens).map(token => (
                      <Table.Tr key={`${suggestion.id}-${token.index}`}>
                        <Table.Td>
                          <Text fw={650} size="sm">
                            {token.token}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Select
                            aria-label={`UPOS tag for ${token.token}`}
                            data={UPOS_TAGS.map(tag => ({ value: tag, label: tag }))}
                            name={`upos-${suggestion.id}-${token.index}`}
                            size="xs"
                            value={token.suggested_pos}
                            onChange={value => onTokenChange(suggestion.id, token.index, value)}
                          />
                        </Table.Td>
                        <Table.Td>
                          <Text c="dimmed" size="xs">
                            {token.rationale}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
                <Group gap="xs">
                  <Button color="green" disabled={working} onClick={() => onReview(suggestion, "approved")} size="xs">
                    Approve
                  </Button>
                  <Button
                    color="violet"
                    disabled={working}
                    onClick={() => onReview(suggestion, "edited")}
                    size="xs"
                    variant="light"
                  >
                    Save Edit
                  </Button>
                  <Button color="red" disabled={working} onClick={() => onReview(suggestion, "denied")} size="xs" variant="light">
                    Deny
                  </Button>
                </Group>
              </Stack>
            </Card>
          ))
        )}
      </Stack>
    </PaperPanel>
  );
}

function ImportsTable({ imports }: { imports: ImportRecord[] }) {
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
          <Text maw={280} size="sm" truncate>
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

function OcrReviewPanel({
  suggestions,
  drafts,
  working,
  onDraftChange,
  onReview,
}: {
  suggestions: Suggestion[];
  drafts: TextDraftMap;
  working: boolean;
  onDraftChange: (id: string, value: string) => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
}) {
  return (
    <PaperPanel title="OCR suggestions" eyebrow="Human validation">
      <Stack gap="md">
        {suggestions.length === 0 ? (
          <Text c="dimmed" size="sm">
            No pending OCR suggestions.
          </Text>
        ) : (
          suggestions.map(suggestion => (
            <Card
              key={suggestion.id}
              withBorder
              radius="md"
              p="md"
              style={{ background: UI.panelSoft, borderColor: UI.border }}
            >
              <Stack gap="sm">
                <Group justify="space-between">
                  <Text fw={750}>{suggestion.original_text}</Text>
                  <Badge color="grape" radius="sm" variant="light">
                    {formatPercent(suggestion.confidence)}
                  </Badge>
                </Group>
                <Textarea
                  aria-label={`OCR text for ${suggestion.original_text}`}
                  autoComplete="off"
                  minRows={5}
                  name={`ocr-${suggestion.id}`}
                  value={drafts[suggestion.id] ?? suggestion.suggested_text ?? ""}
                  onChange={event => onDraftChange(suggestion.id, event.currentTarget.value)}
                />
                <Text c="dimmed" size="xs">
                  {suggestion.rationale}
                </Text>
                <Group gap="xs">
                  <Button color="green" disabled={working} onClick={() => onReview(suggestion, "approved")} size="xs">
                    Approve
                  </Button>
                  <Button
                    color="violet"
                    disabled={working}
                    onClick={() => onReview(suggestion, "edited")}
                    size="xs"
                    variant="light"
                  >
                    Save Edit
                  </Button>
                  <Button color="red" disabled={working} onClick={() => onReview(suggestion, "denied")} size="xs" variant="light">
                    Deny
                  </Button>
                </Group>
              </Stack>
            </Card>
          ))
        )}
      </Stack>
    </PaperPanel>
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
