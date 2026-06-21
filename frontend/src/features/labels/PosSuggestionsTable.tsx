import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Divider,
  Group,
  Modal,
  ScrollArea,
  Select,
  Stack,
  Table,
  Text,
  Tooltip,
} from "@mantine/core";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { TbEye, TbWand } from "react-icons/tb";

import { LoadingBlock } from "@/components/ui/LoadingBlock";
import { PaginatedTableFooter } from "@/components/ui/PaginatedTableFooter";
import { PaperPanel } from "@/components/ui/PaperPanel";
import { PreviewTextButton } from "@/components/ui/PreviewTextButton";
import { UPOS_TAGS } from "@/lib/constants";
import { formatPercent, statusColor } from "@/lib/format";
import type {
  AnnotationRow,
  DetailContent,
  DraftMap,
  PaginationMeta,
  ResearchArtifact,
  ReviewFilter,
  Suggestion,
  SuggestionStatus,
  TokenSuggestion,
} from "@/types/domain";

import { SuggestionActions } from "./SuggestionActions";

function annotationStatus(row: AnnotationRow) {
  if (row.pending_suggestion) return "Pending review";
  if (row.label) return "Reviewed";
  return "Needs suggestion";
}

function annotationStatusColor(row: AnnotationRow) {
  if (row.pending_suggestion) return "yellow";
  if (row.label) return "green";
  return "gray";
}

function tokensFromLabel(label: AnnotationRow["label"]): TokenSuggestion[] {
  const tokens = label?.value["tokens"];
  if (!Array.isArray(tokens)) return [];
  return tokens.flatMap((token, fallbackIndex): TokenSuggestion[] => {
    if (!token || typeof token !== "object") return [];
    const record = token as Record<string, unknown>;
    const tokenText = typeof record["token"] === "string" ? record["token"] : "";
    const suggestedPos = typeof record["suggested_pos"] === "string" ? record["suggested_pos"] : "";
    if (!tokenText || !suggestedPos) return [];
    const index = typeof record["index"] === "number" ? record["index"] : fallbackIndex;
    const confidence = typeof record["confidence"] === "number" ? record["confidence"] : 0;
    const rationale = typeof record["rationale"] === "string" ? record["rationale"] : "";
    return [{ index, token: tokenText, suggested_pos: suggestedPos, confidence, rationale }];
  });
}

function tagsFromLabel(label: AnnotationRow["label"]) {
  const tags = label?.value["tags"];
  return typeof tags === "string" ? tags : "";
}

export function PosSuggestionsTable({
  rows,
  tokenDrafts,
  pagination,
  pageIndex,
  pendingSuggestionTotal,
  reviewFilter,
  research,
  loading,
  working,
  onGenerate,
  onOpenDetail,
  onPageChange,
  onReviewFilterChange,
  onReview,
  onTokenChange,
}: {
  rows: AnnotationRow[];
  tokenDrafts: DraftMap;
  pagination: PaginationMeta;
  pageIndex: number;
  pendingSuggestionTotal: number;
  reviewFilter: ReviewFilter;
  research: ResearchArtifact | null;
  loading: boolean;
  working: boolean;
  onGenerate: () => void;
  onOpenDetail: (detail: DetailContent) => void;
  onPageChange: (pageIndex: number) => void;
  onReviewFilterChange: (filter: ReviewFilter) => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
  onTokenChange: (suggestionId: string, tokenIndex: number, tag: string | null) => void;
}) {
  const [reviewingSuggestion, setReviewingSuggestion] = useState<Suggestion | null>(null);
  const reviewingRow = useMemo(
    () => rows.find(row => row.pending_suggestion?.id === reviewingSuggestion?.id) ?? null,
    [rows, reviewingSuggestion],
  );

  function openSavedLabelDetail(row: AnnotationRow) {
    const label = row.label;
    if (!label) return;
    const tokens = tokensFromLabel(label);
    const csvTags = tagsFromLabel(label);
    onOpenDetail({
      title: "Reviewed POS Label",
      rows: [
        { label: "Text", value: row.text },
        {
          label: "Tags",
          value: tokens.length > 0 ? (
            <Stack gap={6}>
              {tokens.map(token => (
                <Group key={`${label.id}-${token.index}`} gap="xs" wrap="wrap">
                  <Badge color="gray" radius="sm" variant="light">
                    {token.token}
                  </Badge>
                  <Badge color="violet" radius="sm" variant="light">
                    {token.suggested_pos}
                  </Badge>
                  <Text c="dimmed" size="xs">
                    {formatPercent(token.confidence)}
                  </Text>
                </Group>
              ))}
            </Stack>
          ) : (
            csvTags || "No POS tags saved"
          ),
        },
        { label: "Source", value: label.source },
        { label: "Label ID", value: label.id },
      ],
    });
  }

  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<AnnotationRow>();

    return [
      columnHelper.accessor("text", {
        header: "Text",
        cell: info => (
          <Box maw={320} miw={200}>
            <PreviewTextButton
              text={info.getValue()}
              title="POS Text"
              onOpen={() => {
                const row = info.row.original;
                onOpenDetail({
                  title: "POS Row",
                  rows: [
                    { label: "Text", value: row.text },
                    { label: "Status", value: annotationStatus(row) },
                    { label: "Row ID", value: row.data_row_id },
                  ],
                });
              }}
            />
          </Box>
        ),
      }),
      columnHelper.display({
        id: "status",
        header: "Status",
        cell: info => {
          const row = info.row.original;
          return (
            <Badge color={annotationStatusColor(row)} radius="sm" variant={row.pending_suggestion ? "dot" : "light"}>
              {annotationStatus(row)}
            </Badge>
          );
        },
      }),
      columnHelper.display({
        id: "suggestion",
        header: "AI Suggestion",
        cell: info => {
          const row = info.row.original;
          const suggestion = row.pending_suggestion;
          if (suggestion) {
            return (
              <Tooltip label="Review suggestion">
                <ActionIcon aria-label="Review POS suggestion" onClick={() => setReviewingSuggestion(suggestion)} variant="light">
                  <TbEye aria-hidden="true" size={17} />
                </ActionIcon>
              </Tooltip>
            );
          }
          if (!row.label) {
            return null;
          }
          return (
            <Tooltip label="View saved POS label">
              <ActionIcon aria-label="View saved POS label" color="teal" onClick={() => openSavedLabelDetail(row)} variant="light">
                <TbEye aria-hidden="true" size={17} />
              </ActionIcon>
            </Tooltip>
          );
        },
      }),
    ];
  }, [onOpenDetail]);

  const table = useReactTable({
    columns,
    data: rows,
    getCoreRowModel: getCoreRowModel(),
  });

  function reviewAndClose(suggestion: Suggestion, action: SuggestionStatus) {
    onReview(suggestion, action);
    setReviewingSuggestion(null);
  }

  const modalTokens = reviewingSuggestion ? tokenDrafts[reviewingSuggestion.id] ?? reviewingSuggestion.tokens : [];
  const modalText = reviewingRow?.text ?? reviewingSuggestion?.original_text ?? "";

  return (
    <PaperPanel title="POS Tagging" eyebrow="Text, tags, suggestions">
      <Stack gap="md">
        <Group align="center" justify="space-between" wrap="wrap">
          <Group gap="sm" wrap="wrap">
            <Text c="dimmed" size="sm">
              Rows: {pagination.total} | Pending suggestions: {pendingSuggestionTotal}
            </Text>
            <Group aria-label="POS review filter" gap={4} role="group">
              <Button
                color={reviewFilter === "all" ? "violet" : "gray"}
                onClick={() => onReviewFilterChange("all")}
                size="compact-xs"
                variant={reviewFilter === "all" ? "filled" : "subtle"}
              >
                All
              </Button>
              <Button
                color={reviewFilter === "needs_review" ? "violet" : "gray"}
                onClick={() => onReviewFilterChange("needs_review")}
                size="compact-xs"
                variant={reviewFilter === "needs_review" ? "filled" : "subtle"}
              >
                Review
              </Button>
            </Group>
          </Group>
          <Button disabled={working || !research} leftSection={<TbWand aria-hidden="true" size={16} />} onClick={onGenerate}>
            Generate 5 Suggestions
          </Button>
        </Group>
        {!research ? (
          <Text c="dimmed" size="sm">
            Run POS research before generating POS suggestions.
          </Text>
        ) : null}
        {loading ? (
          <LoadingBlock message="Loading POS rows..." />
        ) : rows.length === 0 ? (
          <Text c="dimmed" size="sm">
            {reviewFilter === "needs_review"
              ? "No pending POS suggestions to review."
              : "No POS rows yet. Seed POS rows from translation data or upload POS text."}
          </Text>
        ) : (
          <ScrollArea type="auto">
            <Table miw={820} highlightOnHover>
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

      <Modal
        centered
        onClose={() => setReviewingSuggestion(null)}
        opened={reviewingSuggestion !== null}
        overlayProps={{ backgroundOpacity: 0.74, blur: 3 }}
        padding="lg"
        radius="md"
        scrollAreaComponent={ScrollArea.Autosize}
        shadow="xl"
        size="lg"
        title="Review POS Suggestion"
      >
        {reviewingSuggestion ? (
          <Stack gap="md">
            <Box>
              <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                Text
              </Text>
              <Text size="sm" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {modalText || "No source text"}
              </Text>
            </Box>
            <Box>
              <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                Tokens
              </Text>
              <ScrollArea.Autosize mah={320} type="auto">
                <Stack gap={8} pt={4}>
                  {modalTokens.map(token => (
                    <Group key={`${reviewingSuggestion.id}-${token.index}`} gap="xs" wrap="nowrap">
                      <Badge color="gray" miw={110} radius="sm" variant="light">
                        {token.token}
                      </Badge>
                      <Select
                        aria-label={`UPOS tag for ${token.token}`}
                        data={UPOS_TAGS.map(tag => ({ value: tag, label: tag }))}
                        onChange={value => onTokenChange(reviewingSuggestion.id, token.index, value)}
                        size="xs"
                        value={token.suggested_pos}
                        w={120}
                      />
                      <Text c="dimmed" size="xs">
                        {formatPercent(token.confidence)}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </ScrollArea.Autosize>
            </Box>
            <Group gap="xs">
              <Badge color={statusColor(reviewingSuggestion.status)} radius="sm" variant="dot">
                {reviewingSuggestion.status}
              </Badge>
              <Badge color="grape" radius="sm" variant="light">
                {formatPercent(reviewingSuggestion.confidence)}
              </Badge>
            </Group>
            <Text c="dimmed" size="sm">
              {reviewingSuggestion.rationale || "Review the suggested UPOS tags."}
            </Text>
            <Divider />
            <SuggestionActions suggestion={reviewingSuggestion} working={working} onReview={reviewAndClose} />
          </Stack>
        ) : null}
      </Modal>
    </PaperPanel>
  );
}
