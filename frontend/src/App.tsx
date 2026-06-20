import {
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
} from "@mantine/core";
import { useEffect, useMemo, useState } from "react";

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
  borderStrong: "rgba(168, 85, 247, 0.32)",
};

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
  const [activeTab, setActiveTab] = useState<string | null>("pos");

  const [datasetName, setDatasetName] = useState("Nahuatl field notes");
  const [languageCode, setLanguageCode] = useState("nah");
  const [languageName, setLanguageName] = useState("Nahuatl");
  const [manualText, setManualText] = useState("muchas flores son blancas\nel agua corre rapido");
  const [manualSource, setManualSource] = useState<SourceType>("text");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [translateText, setTranslateText] = useState("muchas flores son blancas");
  const [translation, setTranslation] = useState("");
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
    const created = await runAction(
      () =>
        api<Dataset>("/datasets", {
          method: "POST",
          body: JSON.stringify({
            name: datasetName,
            language_code: languageCode,
            language_name: languageName,
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

  async function translateNahuatl() {
    await runAction(async () => {
      const response = await api<{ output_text: string; provider: string }>("/models/nahuatl/translate", {
        method: "POST",
        body: JSON.stringify({ text: translateText, direction: "spanish_to_nahuatl" }),
      });
      setTranslation(`${response.output_text} (${response.provider})`);
      return response;
    }, "Translation generated");
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

  if (loading) {
    return (
      <Box bg={UI.background} mih="100vh" p="xl">
        <Group justify="center" mt="20vh">
          <Loader color="violet" />
          <Text c="dimmed">Loading workspace</Text>
        </Group>
      </Box>
    );
  }

  return (
    <AppShell
      header={{ height: 64 }}
      navbar={{ width: 300, breakpoint: "sm", collapsed: { mobile: false } }}
      padding={0}
    >
      <AppShell.Header
        style={{
          background: UI.header,
          borderBottom: `1px solid ${UI.border}`,
        }}
      >
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <ThemeIcon color="violet" radius="md" size={38} variant="filled">
              LB
            </ThemeIcon>
            <Box>
              <Title order={1} size="h3" lh={1}>
                LangBase
              </Title>
              <Text c="dimmed" size="xs">
                Low-resource dataset workspace
              </Text>
            </Box>
          </Group>
          <Group gap="xs">
            {working ? <Loader size="sm" /> : null}
            <Badge color={statusColor(dashboard?.pos_model.status ?? "not_started")} radius="sm" variant="light">
              POS model {dashboard?.pos_model.status.replaceAll("_", " ") ?? "not started"}
            </Badge>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar
        style={{
          background: UI.navbar,
          borderRight: `1px solid ${UI.border}`,
        }}
      >
        <Stack gap="sm" h="100%" p="sm">
          <Box px="xs" py="sm">
            <Text c="dimmed" fw={700} size="xs" tt="uppercase">
              Datasets
            </Text>
            <Text c="dimmed" size="xs">
              One cached research profile per dataset and language.
            </Text>
          </Box>

          <ScrollArea flex={1} type="hover">
            <Stack gap={4}>
              {datasets.map(dataset => (
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
              ))}
            </Stack>
          </ScrollArea>

          <Divider />
          <Stack gap="xs">
            <TextInput label="Dataset" size="xs" value={datasetName} onChange={event => setDatasetName(event.currentTarget.value)} />
            <Group grow>
              <TextInput label="Code" size="xs" value={languageCode} onChange={event => setLanguageCode(event.currentTarget.value)} />
              <TextInput label="Language" size="xs" value={languageName} onChange={event => setLanguageName(event.currentTarget.value)} />
            </Group>
            <Button color="green" disabled={working} onClick={() => void createDataset()} size="xs">
              Create Dataset
            </Button>
          </Stack>
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main style={{ background: UI.background, minHeight: "100vh" }}>
        <Box w="100%" maw={1480} mx="auto" px={{ base: "sm", sm: "lg" }} py="lg">
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

            <Paper
              withBorder
              radius="md"
              p="lg"
              style={{ background: UI.panel, borderColor: UI.borderStrong }}
            >
              <Group justify="space-between" align="flex-start" gap="md">
                <Box>
                  <Text c="violet.3" fw={700} size="xs" tt="uppercase">
                    {selectedDataset?.language_name ?? "Language"} corpus
                  </Text>
                  <Title order={2}>{selectedDataset?.name ?? "Dataset workspace"}</Title>
                  <Text c="dimmed" mt={4} maw={720}>
                    Upload sentences and source documents, cache research notes once, review AI suggestions in batches,
                    and trigger a dataset-specific UPOS tagger.
                  </Text>
                </Box>
                <Group gap="xs">
                  <Badge color="violet" radius="sm" variant="light">
                    {dashboard?.item_count ?? 0} text items
                  </Badge>
                  <Badge color="yellow" radius="sm" variant="light">
                    {pendingPosCount} POS pending
                  </Badge>
                  <Badge color="green" radius="sm" variant="light">
                    {acceptedPosCount} accepted
                  </Badge>
                </Group>
              </Group>
            </Paper>

            <SimpleGrid cols={{ base: 1, md: 4 }} spacing="md">
              <MetricCard label="Research" value={dashboard?.research ? "Cached" : "Not run"} tone="violet" />
              <MetricCard label="Imports" value={`${dashboard?.imports.length ?? 0}`} tone="green" />
              <MetricCard label="OCR Review" value={`${pendingOcrCount} pending`} tone="grape" />
              <MetricCard label="POS Model" value={dashboard?.pos_model.model_name ?? "Demo trigger"} tone="lime" />
            </SimpleGrid>

            <Tabs value={activeTab} onChange={setActiveTab} radius="md" variant="pills">
              <Tabs.List>
                <Tabs.Tab value="pos">POS Review</Tabs.Tab>
                <Tabs.Tab value="uploads">Uploads</Tabs.Tab>
                <Tabs.Tab value="ocr">OCR</Tabs.Tab>
                <Tabs.Tab value="model">Model Demo</Tabs.Tab>
              </Tabs.List>

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
                </SimpleGrid>
              </Tabs.Panel>

              <Tabs.Panel value="uploads" pt="md">
                <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
                  <PaperPanel title="Manual sentences" eyebrow="Text import">
                    <Stack gap="sm">
                      <Select
                        data={[
                          { value: "text", label: "Manual text" },
                          { value: "csv", label: "CSV text" },
                          { value: "txt", label: "TXT lines" },
                        ]}
                        label="Source type"
                        value={manualSource}
                        onChange={value => setManualSource((value as SourceType | null) ?? "text")}
                      />
                      <Textarea
                        autosize
                        minRows={8}
                        label="Sentences"
                        value={manualText}
                        onChange={event => setManualText(event.currentTarget.value)}
                      />
                      <Button color="green" disabled={working || !manualText.trim()} onClick={() => void importManualText()}>
                        Import Sentences
                      </Button>
                    </Stack>
                  </PaperPanel>

                  <PaperPanel title="Files and imports" eyebrow="CSV, TXT, PDF, image">
                    <Stack gap="md">
                      <Group align="end">
                        <FileInput
                          flex={1}
                          label="Upload file"
                          placeholder="Choose CSV, TXT, PDF, or image"
                          value={uploadFile}
                          onChange={setUploadFile}
                        />
                        <Button color="green" disabled={working || !uploadFile} onClick={() => void importFile()}>
                          Upload
                        </Button>
                      </Group>
                      <ImportsTable imports={dashboard?.imports ?? []} />
                    </Stack>
                  </PaperPanel>
                </SimpleGrid>
              </Tabs.Panel>

              <Tabs.Panel value="ocr" pt="md">
                <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
                  <PaperPanel title="OCR queue" eyebrow="PDF and image extraction">
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

              <Tabs.Panel value="model" pt="md">
                <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
                  <PaperPanel title="Spanish to Nahuatl" eyebrow="Hugging Face T5 demo endpoint">
                    <Stack gap="sm">
                      <Textarea
                        label="Spanish input"
                        minRows={4}
                        value={translateText}
                        onChange={event => setTranslateText(event.currentTarget.value)}
                      />
                      <Button color="green" disabled={working || !translateText.trim()} onClick={() => void translateNahuatl()}>
                        Translate
                      </Button>
                      {translation ? (
                        <Card withBorder radius="md" p="md" style={{ background: UI.panelSoft, borderColor: UI.border }}>
                          <Text fw={700}>{translation}</Text>
                        </Card>
                      ) : null}
                    </Stack>
                  </PaperPanel>

                  <PaperPanel title="Dataset POS tagger" eyebrow="Training trigger">
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
            </Tabs>

            <JobsPanel jobs={jobs} />
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

function PaperPanel({ title, eyebrow, children }: { title: string; eyebrow: string; children: React.ReactNode }) {
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
                            data={UPOS_TAGS.map(tag => ({ value: tag, label: tag }))}
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
          <Table.Tr>
            <Table.Th>Source</Table.Th>
            <Table.Th>File</Table.Th>
            <Table.Th>Items</Table.Th>
            <Table.Th>Status</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {imports.map(item => (
            <Table.Tr key={item.id}>
              <Table.Td>
                <Badge color={sourceColor(item.source_type)} radius="sm" variant="light">
                  {item.source_type}
                </Badge>
              </Table.Td>
              <Table.Td>{item.filename ?? "manual import"}</Table.Td>
              <Table.Td>{item.item_count || item.asset_count}</Table.Td>
              <Table.Td>
                <Badge color={statusColor(item.status)} radius="sm" variant="dot">
                  {item.status}
                </Badge>
              </Table.Td>
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
                  minRows={5}
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
