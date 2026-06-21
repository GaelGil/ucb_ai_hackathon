import { Badge, Box, Button, Group, ScrollArea, Stack, Table, Text, Textarea } from "@mantine/core";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useMemo } from "react";

import { LoadingBlock } from "@/components/ui/LoadingBlock";
import { PaginatedTableFooter } from "@/components/ui/PaginatedTableFooter";
import { PaperPanel } from "@/components/ui/PaperPanel";
import { PreviewTextButton } from "@/components/ui/PreviewTextButton";
import { formatPercent, statusColor } from "@/lib/format";
import type {
  DetailContent,
  ImportRecord,
  PaginationMeta,
  Suggestion,
  SuggestionStatus,
  TextDraftMap,
} from "@/types/domain";

import { SuggestionActions } from "./SuggestionActions";

export function OcrSuggestionsTable({
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
