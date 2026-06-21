import { Badge, Box, Button, Divider, Group, ScrollArea, Stack, Table, Text, Textarea } from "@mantine/core";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useMemo } from "react";

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
} from "@/types/domain";

import { SuggestionActions } from "./SuggestionActions";

export function TranslationTable({
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
