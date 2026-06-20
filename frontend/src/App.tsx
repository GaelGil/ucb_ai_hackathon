import {
  AppShell,
  Badge,
  Box,
  Burger,
  Card,
  Group,
  NavLink,
  Paper,
  ScrollArea,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  ThemeIcon,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
} from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";

type Language = {
  code: string;
  name: string;
  region: string;
  script: string;
  sample: string;
};

type TaskCategory = "all" | "open-source" | "pos" | "ocr" | "upload";
type SourceTag = "Image" | "PDF" | "Text";
type SourceFilter = SourceTag | "All";
type TaskStatus = "Ready" | "Review" | "Queued" | "Synced";

type TaskRow = {
  id: string;
  languageCode: string;
  title: string;
  category: Exclude<TaskCategory, "all">;
  source: SourceTag;
  status: TaskStatus;
  score: string;
  updated: string;
};

type TaskCard = {
  id: TaskCategory;
  label: string;
  description: string;
  stat: string;
  tone: "blue" | "cyan" | "teal" | "orange" | "grape";
};

const languages: Language[] = [
  { code: "en", name: "English", region: "Global", script: "Latin", sample: "Community moderation" },
  { code: "es", name: "Spanish", region: "Latin America", script: "Latin", sample: "Policy summaries" },
  { code: "fr", name: "French", region: "West Africa", script: "Latin", sample: "Health forms" },
  { code: "hi", name: "Hindi", region: "India", script: "Devanagari", sample: "Public notices" },
  { code: "ar", name: "Arabic", region: "MENA", script: "Arabic", sample: "Civic records" },
  { code: "sw", name: "Swahili", region: "East Africa", script: "Latin", sample: "Education content" },
  { code: "pt", name: "Portuguese", region: "Brazil", script: "Latin", sample: "Support tickets" },
  { code: "zh", name: "Mandarin", region: "China", script: "Simplified", sample: "Dataset review" },
];

const taskCards: TaskCard[] = [
  {
    id: "all",
    label: "All",
    description: "Every active item for the selected language.",
    stat: "24 rows",
    tone: "blue",
  },
  {
    id: "open-source",
    label: "Open Source Contributions",
    description: "Community translations, issue triage, and dataset patches.",
    stat: "8 merged",
    tone: "cyan",
  },
  {
    id: "pos",
    label: "Part-Of-Speech Tagging",
    description: "Token labeling, review queues, and quality checks.",
    stat: "96.4%",
    tone: "teal",
  },
  {
    id: "ocr",
    label: "OCR",
    description: "Image and PDF extraction runs awaiting validation.",
    stat: "14 scans",
    tone: "orange",
  },
  {
    id: "upload",
    label: "Upload",
    description: "Incoming files and text batches ready to process.",
    stat: "6 new",
    tone: "grape",
  },
];

const sourceFilters: SourceFilter[] = ["All", "Image", "PDF", "Text"];

const rows: TaskRow[] = languages.flatMap((language, languageIndex) => [
  {
    id: `${language.code}-open-source-issue`,
    languageCode: language.code,
    title: `${language.name} glossary pull request`,
    category: "open-source",
    source: "Text",
    status: languageIndex % 2 === 0 ? "Synced" : "Review",
    score: `${42 + languageIndex} edits`,
    updated: "Jun 18, 2026",
  },
  {
    id: `${language.code}-open-source-corpus`,
    languageCode: language.code,
    title: `${language.sample} corpus cleanup`,
    category: "open-source",
    source: "PDF",
    status: "Ready",
    score: `${18 + languageIndex} files`,
    updated: "Jun 17, 2026",
  },
  {
    id: `${language.code}-pos-annotation`,
    languageCode: language.code,
    title: `${language.script} POS annotation batch`,
    category: "pos",
    source: "Text",
    status: "Ready",
    score: `${94 + (languageIndex % 4)}%`,
    updated: "Jun 16, 2026",
  },
  {
    id: `${language.code}-pos-review`,
    languageCode: language.code,
    title: `${language.region} grammar review set`,
    category: "pos",
    source: "PDF",
    status: "Queued",
    score: `${1_200 + languageIndex * 80} tokens`,
    updated: "Jun 15, 2026",
  },
  {
    id: `${language.code}-ocr-image`,
    languageCode: language.code,
    title: `${language.name} signage OCR run`,
    category: "ocr",
    source: "Image",
    status: languageIndex % 3 === 0 ? "Review" : "Ready",
    score: `${88 + (languageIndex % 8)}%`,
    updated: "Jun 14, 2026",
  },
  {
    id: `${language.code}-ocr-doc`,
    languageCode: language.code,
    title: `${language.sample} PDF extraction`,
    category: "ocr",
    source: "PDF",
    status: "Synced",
    score: `${12 + languageIndex} pages`,
    updated: "Jun 13, 2026",
  },
  {
    id: `${language.code}-upload-image`,
    languageCode: language.code,
    title: `${language.name} image upload queue`,
    category: "upload",
    source: "Image",
    status: "Queued",
    score: `${5 + languageIndex} assets`,
    updated: "Jun 12, 2026",
  },
  {
    id: `${language.code}-upload-text`,
    languageCode: language.code,
    title: `${language.region} text test import`,
    category: "upload",
    source: "Text",
    status: "Ready",
    score: `${2 + languageIndex} batches`,
    updated: "Jun 11, 2026",
  },
]);

const defaultLanguageCode = languages[0]?.code ?? "en";
const categoryLabels = new Map<TaskCategory, string>(taskCards.map(card => [card.id, card.label]));
const categoryValues = new Set<TaskCategory>(taskCards.map(card => card.id));
const sourceValues = new Set<SourceFilter>(sourceFilters);

function categoryLabel(category: TaskCategory | Exclude<TaskCategory, "all">) {
  return categoryLabels.get(category) ?? category;
}

function initialLanguageCode() {
  if (typeof window === "undefined") return defaultLanguageCode;

  const languageParam = new URLSearchParams(window.location.search).get("lang");
  return languages.some(language => language.code === languageParam) ? languageParam! : defaultLanguageCode;
}

function initialCategory() {
  if (typeof window === "undefined") return "all";

  const viewParam = new URLSearchParams(window.location.search).get("view") as TaskCategory | null;
  return viewParam && categoryValues.has(viewParam) ? viewParam : "all";
}

function initialSourceFilter() {
  if (typeof window === "undefined") return "All";

  const sourceParam = new URLSearchParams(window.location.search).get("source");
  const normalized = sourceFilters.find(source => source.toLowerCase() === sourceParam?.toLowerCase());
  return normalized ?? "All";
}

function statusColor(status: TaskStatus) {
  switch (status) {
    case "Ready":
      return "green";
    case "Review":
      return "yellow";
    case "Queued":
      return "gray";
    case "Synced":
      return "blue";
  }
}

function sourceColor(source: SourceTag) {
  switch (source) {
    case "Image":
      return "orange";
    case "PDF":
      return "red";
    case "Text":
      return "teal";
  }
}

const columns: ColumnDef<TaskRow>[] = [
  {
    accessorKey: "title",
    header: "Item",
    cell: info => (
      <Text fw={650} size="sm">
        {info.getValue<string>()}
      </Text>
    ),
  },
  {
    accessorKey: "category",
    header: "Task",
    filterFn: "equalsString",
    cell: info => (
      <Text c="dimmed" size="sm">
        {categoryLabel(info.getValue<Exclude<TaskCategory, "all">>())}
      </Text>
    ),
  },
  {
    accessorKey: "source",
    header: "Source",
    filterFn: "equalsString",
    cell: info => {
      const source = info.getValue<SourceTag>();
      return (
        <Badge color={sourceColor(source)} radius="sm" variant="light">
          {source}
        </Badge>
      );
    },
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: info => {
      const status = info.getValue<TaskStatus>();
      return (
        <Badge color={statusColor(status)} radius="sm" variant="dot">
          {status}
        </Badge>
      );
    },
  },
  {
    accessorKey: "score",
    header: "Score",
    cell: info => (
      <Text ff="monospace" size="sm">
        {info.getValue<string>()}
      </Text>
    ),
  },
  {
    accessorKey: "updated",
    header: "Updated",
    cell: info => (
      <Text c="dimmed" size="sm">
        {info.getValue<string>()}
      </Text>
    ),
  },
];

export function App() {
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure();
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);
  const [selectedLanguageCode, setSelectedLanguageCode] = useState(initialLanguageCode);
  const [activeCategory, setActiveCategory] = useState<TaskCategory>(initialCategory);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>(initialSourceFilter);

  const selectedLanguage = useMemo(
    () => languages.find(language => language.code === selectedLanguageCode) ?? languages[0],
    [selectedLanguageCode],
  );

  const selectedLanguageRows = useMemo(
    () => rows.filter(row => row.languageCode === selectedLanguageCode),
    [selectedLanguageCode],
  );

  const columnFilters = useMemo<ColumnFiltersState>(() => {
    const filters: ColumnFiltersState = [];

    if (activeCategory !== "all") {
      filters.push({ id: "category", value: activeCategory });
    }

    if (sourceFilter !== "All") {
      filters.push({ id: "source", value: sourceFilter });
    }

    return filters;
  }, [activeCategory, sourceFilter]);

  const table = useReactTable({
    data: selectedLanguageRows,
    columns,
    state: { columnFilters },
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const visibleRows = table.getRowModel().rows;
  const activeCard = taskCards.find(card => card.id === activeCategory) ?? taskCards[0];

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set("lang", selectedLanguageCode);
    params.set("view", activeCategory);
    params.set("source", sourceFilter.toLowerCase());

    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}${window.location.hash}`);
  }, [activeCategory, selectedLanguageCode, sourceFilter]);

  const selectLanguage = (languageCode: string) => {
    setSelectedLanguageCode(languageCode);
    setActiveCategory("all");
    setSourceFilter("All");
    closeMobile();
  };

  return (
    <AppShell
      header={{ height: 64 }}
      navbar={{ width: desktopCollapsed ? 92 : 304, breakpoint: "sm", collapsed: { mobile: !mobileOpened } }}
      padding={0}
    >
      <AppShell.Header
        style={{
          background: "rgba(9, 14, 28, 0.92)",
          backdropFilter: "blur(18px)",
          borderBottom: "1px solid rgba(148, 163, 184, 0.16)",
        }}
      >
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={mobileOpened} onClick={toggleMobile} hiddenFrom="sm" size="sm" aria-label="Toggle sidebar" />
            <Burger
              opened={!desktopCollapsed}
              onClick={() => setDesktopCollapsed(collapsed => !collapsed)}
              visibleFrom="sm"
              size="sm"
              aria-label={desktopCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            />
            <ThemeIcon
              radius="md"
              size={38}
              variant="filled"
              style={{
                background: "linear-gradient(135deg, #3b82f6, #14b8a6)",
                color: "white",
                fontSize: "0.78rem",
                fontWeight: 900,
                letterSpacing: 0,
              }}
            >
              LB
            </ThemeIcon>
            <Box>
              <Title order={1} size="h3" lh={1}>
                LangBase
              </Title>
              <Text c="dimmed" size="xs" visibleFrom="sm">
                Language intelligence workspace
              </Text>
            </Box>
          </Group>

          <Badge color="blue" radius="sm" variant="light">
            {selectedLanguage?.name ?? "Language"} active
          </Badge>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar
        style={{
          background: "#0d1326",
          borderRight: "1px solid rgba(148, 163, 184, 0.16)",
        }}
      >
        <Stack gap="xs" h="100%" p="sm">
          {!desktopCollapsed ? (
            <Box px="xs" py="sm">
              <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                Languages
              </Text>
              <Text c="dimmed" size="xs">
                Pick a workspace corpus.
              </Text>
            </Box>
          ) : null}

          <ScrollArea flex={1} type="hover">
            <Stack gap={4}>
              {languages.map(language => (
                <NavLink
                  key={language.code}
                  active={language.code === selectedLanguageCode}
                  aria-label={`Select ${language.name}`}
                  description={desktopCollapsed ? undefined : `${language.region} - ${language.script}`}
                  label={desktopCollapsed ? language.code.toUpperCase() : language.name}
                  leftSection={
                    <ThemeIcon radius="md" size={34} variant={language.code === selectedLanguageCode ? "filled" : "light"}>
                      {language.code.toUpperCase()}
                    </ThemeIcon>
                  }
                  onClick={() => selectLanguage(language.code)}
                  variant="filled"
                />
              ))}
            </Stack>
          </ScrollArea>
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main
        style={{
          background:
            "radial-gradient(circle at top right, rgba(37, 99, 235, 0.18), transparent 34rem), linear-gradient(180deg, #11182d 0%, #0b1020 48%)",
          minHeight: "100vh",
        }}
      >
        <Box w="100%" maw={1440} mx="auto" px={{ base: "sm", sm: "lg" }} py="lg">
          <Stack gap="lg">
            <Paper
              withBorder
              radius="lg"
              p="lg"
              shadow="xl"
              style={{
                background: "rgba(15, 23, 42, 0.76)",
                borderColor: "rgba(148, 163, 184, 0.16)",
                overflow: "hidden",
              }}
            >
              <Group justify="space-between" align="flex-start" gap="md">
                <Box>
                  <Text c="blue.3" fw={700} size="xs" tt="uppercase">
                    {selectedLanguage?.region ?? "Global"} corpus
                  </Text>
                  <Title order={2} size="h1">
                    {selectedLanguage?.name ?? "Language"} dashboard
                  </Title>
                  <Text c="dimmed" mt={4} maw={620}>
                    Track contributions, tagging, OCR, and upload queues from one compact language workspace.
                  </Text>
                </Box>

                <Group gap="xs">
                  <Badge color="gray" radius="sm" variant="outline">
                    {selectedLanguage?.script ?? "Script"}
                  </Badge>
                  <Badge color="blue" radius="sm" variant="light">
                    {selectedLanguageRows.length} rows
                  </Badge>
                </Group>
              </Group>
            </Paper>

            <SimpleGrid cols={{ base: 1, xs: 2, lg: 5 }} spacing="md">
              {taskCards.map(card => (
                <UnstyledButton
                  key={card.id}
                  aria-pressed={activeCategory === card.id}
                  onClick={() => setActiveCategory(card.id)}
                  style={{
                    width: "100%",
                    height: "100%",
                    borderRadius: "var(--mantine-radius-md)",
                  }}
                >
                  <Card
                    withBorder
                    radius="md"
                    p="md"
                    shadow={activeCategory === card.id ? "md" : "sm"}
                    style={{
                      background: activeCategory === card.id ? "rgba(17, 31, 58, 0.92)" : "rgba(15, 23, 42, 0.76)",
                      borderColor:
                        activeCategory === card.id ? "rgba(96, 165, 250, 0.64)" : "rgba(148, 163, 184, 0.16)",
                      height: "100%",
                      minHeight: 164,
                      transition: "border-color 140ms ease, background 140ms ease, transform 140ms ease",
                    }}
                  >
                    <Group justify="space-between" align="flex-start" mb="lg" wrap="nowrap">
                      <ThemeIcon color={card.tone} radius="md" size={38} variant={activeCategory === card.id ? "filled" : "light"}>
                        {card.label.slice(0, 2)}
                      </ThemeIcon>
                      <Badge color={card.tone} radius="sm" variant="light">
                        {card.stat}
                      </Badge>
                    </Group>
                    <Text fw={800} size="sm">
                      {card.label}
                    </Text>
                    <Text c="dimmed" lineClamp={2} mt={6} size="xs">
                      {card.description}
                    </Text>
                  </Card>
                </UnstyledButton>
              ))}
            </SimpleGrid>

            <Paper
              withBorder
              radius="lg"
              shadow="xl"
              style={{
                background: "rgba(15, 23, 42, 0.76)",
                borderColor: "rgba(148, 163, 184, 0.16)",
                overflow: "hidden",
              }}
            >
              <Group justify="space-between" align="flex-start" p="lg" gap="md">
                <Box>
                  <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                    {activeCard?.label ?? "All"} table
                  </Text>
                  <Title order={3} size="h3">
                    {visibleRows.length} matching items
                  </Title>
                </Box>

                <SegmentedControl
                  aria-label="Filter by source type"
                  data={sourceFilters}
                  onChange={value => {
                    if (sourceValues.has(value as SourceFilter)) {
                      setSourceFilter(value as SourceFilter);
                    }
                  }}
                  radius="md"
                  size="xs"
                  value={sourceFilter}
                />
              </Group>

              <ScrollArea type="auto">
                <Table miw={860} highlightOnHover horizontalSpacing="lg" verticalSpacing="md">
                  <Table.Thead>
                    {table.getHeaderGroups().map(headerGroup => (
                      <Table.Tr key={headerGroup.id}>
                        {headerGroup.headers.map(header => (
                          <Table.Th key={header.id} c="dimmed" fz="xs" fw={800} tt="uppercase">
                            {header.isPlaceholder
                              ? null
                              : flexRender(header.column.columnDef.header, header.getContext())}
                          </Table.Th>
                        ))}
                      </Table.Tr>
                    ))}
                  </Table.Thead>
                  <Table.Tbody>
                    {visibleRows.length > 0 ? (
                      visibleRows.map(row => (
                        <Table.Tr key={row.id} bg="rgba(15, 23, 42, 0.36)">
                          {row.getVisibleCells().map(cell => (
                            <Table.Td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</Table.Td>
                          ))}
                        </Table.Tr>
                      ))
                    ) : (
                      <Table.Tr>
                        <Table.Td colSpan={columns.length}>
                          <Text c="dimmed" py="xl" ta="center">
                            No rows match this filter.
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    )}
                  </Table.Tbody>
                </Table>
              </ScrollArea>
            </Paper>
          </Stack>
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}

export default App;
