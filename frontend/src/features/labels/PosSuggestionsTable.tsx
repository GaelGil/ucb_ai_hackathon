import { Badge, Box, Button, Group, ScrollArea, Select, Stack, Table, Text } from "@mantine/core";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useMemo } from "react";

import { PaginatedTableFooter } from "@/components/ui/PaginatedTableFooter";
import { PaperPanel } from "@/components/ui/PaperPanel";
import { PreviewTextButton } from "@/components/ui/PreviewTextButton";
import { LoadingBlock } from "@/components/ui/LoadingBlock";
import { UPOS_TAGS } from "@/lib/constants";
import { formatPercent, formatTokenDetails, statusColor } from "@/lib/format";
import type { DetailContent, DraftMap, PaginationMeta, Suggestion, SuggestionStatus } from "@/types/domain";

import { SuggestionActions } from "./SuggestionActions";

export function PosSuggestionsTable({
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
