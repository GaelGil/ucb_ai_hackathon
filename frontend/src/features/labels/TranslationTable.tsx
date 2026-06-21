import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Divider,
  Group,
  Modal,
  ScrollArea,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Textarea,
  Tooltip,
} from "@mantine/core";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { TbEye, TbWand } from "react-icons/tb";

import { LoadingBlock } from "@/components/ui/LoadingBlock";
import { PaginatedTableFooter } from "@/components/ui/PaginatedTableFooter";
import { PaperPanel } from "@/components/ui/PaperPanel";
import { PreviewTextButton } from "@/components/ui/PreviewTextButton";
import { formatPercent, statusColor, translationValue } from "@/lib/format";
import type {
  DetailContent,
  Label,
  PaginationMeta,
  ResearchArtifact,
  Suggestion,
  SuggestionStatus,
  TextDraftMap,
  TranslationReviewFilter,
} from "@/types/domain";

import { SuggestionActions } from "./SuggestionActions";

export function TranslationTable({
  labels,
  drafts,
  labelsPagination,
  labelsPageIndex,
  pendingSuggestionTotal,
  reviewFilter,
  research,
  loading,
  working,
  onGenerate,
  onOpenDetail,
  onLabelsPageChange,
  onReviewFilterChange,
  onDraftChange,
  onReview,
}: {
  labels: Label[];
  drafts: TextDraftMap;
  labelsPagination: PaginationMeta;
  labelsPageIndex: number;
  pendingSuggestionTotal: number;
  reviewFilter: TranslationReviewFilter;
  research: ResearchArtifact | null;
  loading: boolean;
  working: boolean;
  onGenerate: () => void;
  onOpenDetail: (detail: DetailContent) => void;
  onLabelsPageChange: (pageIndex: number) => void;
  onReviewFilterChange: (filter: TranslationReviewFilter) => void;
  onDraftChange: (id: string, value: string) => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
}) {
  const [reviewingSuggestion, setReviewingSuggestion] = useState<Suggestion | null>(null);
  const reviewingLabel = useMemo(
    () => labels.find(label => label.pending_suggestion?.id === reviewingSuggestion?.id) ?? null,
    [labels, reviewingSuggestion],
  );

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
          <Box maw={260} miw={180}>
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
      columnHelper.display({
        id: "suggestion",
        header: "AI Suggestion",
        cell: info => {
          const suggestion = info.row.original.pending_suggestion;
          if (!suggestion) {
            return null;
          }
          return (
            <Tooltip label="Review suggestion">
              <ActionIcon aria-label="Review suggestion" onClick={() => setReviewingSuggestion(suggestion)} variant="light">
                <TbEye aria-hidden="true" size={17} />
              </ActionIcon>
            </Tooltip>
          );
        },
      }),
    ];
  }, [onOpenDetail]);

  const labelTable = useReactTable({
    columns: labelColumns,
    data: labels,
    getCoreRowModel: getCoreRowModel(),
  });

  function reviewAndClose(suggestion: Suggestion, action: SuggestionStatus) {
    onReview(suggestion, action);
    setReviewingSuggestion(null);
  }

  const modalDraft = reviewingSuggestion ? drafts[reviewingSuggestion.id] ?? reviewingSuggestion.suggested_text ?? "" : "";
  const modalSourceText = reviewingLabel?.data_text ?? reviewingSuggestion?.original_text ?? "";
  const modalCurrentTranslation = reviewingLabel ? translationValue(reviewingLabel) : "";

  return (
    <PaperPanel title="Translate" eyebrow="Labels, research, suggestions">
      <Stack gap="md">
        <Group align="center" justify="space-between" wrap="wrap">
          <Group gap="sm" wrap="wrap">
            <Text c="dimmed" size="sm">
              Saved labels: {labelsPagination.total} | Pending suggestions: {pendingSuggestionTotal}
            </Text>
            <SegmentedControl
              data={[
                { label: "All", value: "all" },
                { label: "Review", value: "needs_review" },
              ]}
              onChange={value => onReviewFilterChange(value as TranslationReviewFilter)}
              size="xs"
              value={reviewFilter}
            />
          </Group>
          <Button disabled={working || !research} leftSection={<TbWand aria-hidden="true" size={16} />} onClick={onGenerate}>
            Generate 5 Suggestions
          </Button>
        </Group>
        {!research ? (
          <Text c="dimmed" size="sm">
            Run translation research before generating translation suggestions.
          </Text>
        ) : null}
        {loading ? (
          <LoadingBlock message="Loading translations..." />
        ) : labels.length === 0 ? (
          <Text c="dimmed" size="sm">
            No translation labels yet. Import a translation CSV or accept AI suggestions.
          </Text>
        ) : (
          <ScrollArea type="auto">
            <Table miw={980} highlightOnHover>
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
        <PaginatedTableFooter
          pagination={labelsPagination}
          pageIndex={labelsPageIndex}
          onPageChange={onLabelsPageChange}
        />
      </Stack>

      <Modal
        centered
        onClose={() => setReviewingSuggestion(null)}
        opened={reviewingSuggestion !== null}
        scrollAreaComponent={ScrollArea.Autosize}
        size="lg"
        title="Review Translation Suggestion"
      >
        {reviewingSuggestion ? (
          <Stack gap="md">
            <Box>
              <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                Source Text
              </Text>
              <Text size="sm" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {modalSourceText || "No source text"}
              </Text>
            </Box>
            <Box>
              <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                Current Translation
              </Text>
              <Text size="sm" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {modalCurrentTranslation || "No saved translation"}
              </Text>
            </Box>
            <Textarea
              autosize
              label="Suggested Translation"
              maxRows={6}
              minRows={3}
              onChange={event => onDraftChange(reviewingSuggestion.id, event.currentTarget.value)}
              value={modalDraft}
            />
            <Group gap="xs">
              <Badge color={statusColor(reviewingSuggestion.status)} radius="sm" variant="dot">
                {reviewingSuggestion.status}
              </Badge>
              <Badge color="grape" radius="sm" variant="light">
                {formatPercent(reviewingSuggestion.confidence)}
              </Badge>
            </Group>
            <Text c="dimmed" size="sm">
              {reviewingSuggestion.rationale || "Review the suggested translation."}
            </Text>
            <Divider />
            <SuggestionActions suggestion={reviewingSuggestion} working={working} onReview={reviewAndClose} />
          </Stack>
        ) : null}
      </Modal>
    </PaperPanel>
  );
}
