import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Divider,
  Group,
  Image,
  Modal,
  MultiSelect,
  ScrollArea,
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
import { API_BASE_URL } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import type {
  ImportRecord,
  OcrRow,
  PaginationMeta,
  Suggestion,
  SuggestionStatus,
  TextDraftMap,
} from "@/types/domain";

import { SuggestionActions } from "./SuggestionActions";

function imageSrc(row: OcrRow) {
  return row.image_url.startsWith("http") ? row.image_url : `${API_BASE_URL}${row.image_url}`;
}

function rowText(row: OcrRow, drafts: TextDraftMap) {
  const suggestion = row.pending_suggestion;
  return suggestion ? drafts[suggestion.id] ?? suggestion.suggested_text ?? row.text : row.text;
}

function statusLabel(row: OcrRow) {
  if (row.pending_suggestion) return "Pending review";
  if (row.status === "reviewed") return "Reviewed";
  return "Not scanned";
}

function statusColor(row: OcrRow) {
  if (row.pending_suggestion) return "yellow";
  if (row.status === "reviewed") return "green";
  return "gray";
}

export function OcrSuggestionsTable({
  latestAssetImport,
  imageImports,
  selectedImportIds,
  rows,
  drafts,
  pagination,
  pageIndex,
  pendingSuggestionTotal,
  loading,
  working,
  onPageChange,
  onRunOcr,
  onRunOcrForImport,
  onSelectedImportIdsChange,
  onDraftChange,
  onReview,
}: {
  latestAssetImport: ImportRecord | null;
  imageImports: ImportRecord[];
  selectedImportIds: string[];
  rows: OcrRow[];
  drafts: TextDraftMap;
  pagination: PaginationMeta;
  pageIndex: number;
  pendingSuggestionTotal: number;
  loading: boolean;
  working: boolean;
  onPageChange: (pageIndex: number) => void;
  onRunOcr: () => void;
  onRunOcrForImport: (importId: string) => void;
  onSelectedImportIdsChange: (ids: string[]) => void;
  onDraftChange: (id: string, value: string) => void;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
}) {
  const [reviewingRow, setReviewingRow] = useState<OcrRow | null>(null);
  const reviewingSuggestion = reviewingRow?.pending_suggestion ?? null;
  const modalText = reviewingRow ? rowText(reviewingRow, drafts) : "";
  const imageOptions = imageImports.map(item => ({
    value: item.id,
    label: item.filename ?? item.id,
  }));

  const columns = useMemo(() => {
    const columnHelper = createColumnHelper<OcrRow>();

    return [
      columnHelper.display({
        id: "image",
        header: "Image",
        cell: info => {
          const row = info.row.original;
          return (
            <Group gap="sm" miw={220} wrap="nowrap">
              <Image
                alt={row.filename}
                fallbackSrc=""
                fit="cover"
                h={72}
                radius="sm"
                src={imageSrc(row)}
                w={96}
              />
              <Box miw={0}>
                <Text fw={700} lineClamp={2} size="sm">
                  {row.filename}
                </Text>
                <Text c="dimmed" size="xs">
                  {row.import_id}
                </Text>
              </Box>
            </Group>
          );
        },
      }),
      columnHelper.display({
        id: "text",
        header: "Extracted Text",
        cell: info => {
          const text = rowText(info.row.original, drafts);
          return (
            <Box maw={360} miw={240}>
              {text ? (
                <Text fw={600} lineClamp={3} size="sm">
                  {text}
                </Text>
              ) : null}
            </Box>
          );
        },
      }),
      columnHelper.display({
        id: "status",
        header: "Status",
        cell: info => {
          const row = info.row.original;
          return (
            <Badge color={statusColor(row)} radius="sm" variant={row.pending_suggestion ? "dot" : "light"}>
              {statusLabel(row)}
            </Badge>
          );
        },
      }),
      columnHelper.display({
        id: "action",
        header: "Review",
        cell: info => {
          const row = info.row.original;
          if (row.status === "not_scanned") {
            return (
              <Button
                disabled={working}
                leftSection={<TbWand aria-hidden="true" size={15} />}
                onClick={() => onRunOcrForImport(row.import_id)}
                size="compact-sm"
                variant="light"
              >
                Scan
              </Button>
            );
          }
          return (
            <Tooltip label={row.pending_suggestion ? "Review OCR text" : "View OCR text"}>
              <ActionIcon aria-label="View OCR row" onClick={() => setReviewingRow(row)} variant="light">
                <TbEye aria-hidden="true" size={17} />
              </ActionIcon>
            </Tooltip>
          );
        },
      }),
    ];
  }, [drafts, onRunOcrForImport, working]);

  const table = useReactTable({
    columns,
    data: rows,
    getCoreRowModel: getCoreRowModel(),
  });

  function reviewAndClose(suggestion: Suggestion, action: SuggestionStatus) {
    onReview(suggestion, action);
    setReviewingRow(null);
  }

  return (
    <PaperPanel title="OCR" eyebrow="Images, literal text, review">
      <Stack gap="md">
        <Group align="end" justify="space-between" wrap="wrap">
          <Stack gap={4} flex={1}>
            <Text c="dimmed" size="sm">
              Images: {pagination.total} | Pending review: {pendingSuggestionTotal}
            </Text>
            <Text c="dimmed" size="xs">
              Latest image import: {latestAssetImport?.filename ?? "No image import yet"}
            </Text>
            <MultiSelect
              aria-label="Image imports for OCR"
              clearable
              data={imageOptions}
              disabled={working || imageOptions.length === 0}
              maxDropdownHeight={220}
              onChange={onSelectedImportIdsChange}
              placeholder="Select image uploads"
              searchable
              value={selectedImportIds}
            />
          </Stack>
          <Button
            disabled={working || selectedImportIds.length === 0}
            leftSection={<TbWand aria-hidden="true" size={16} />}
            onClick={onRunOcr}
          >
            Run OCR
          </Button>
        </Group>
        {loading ? (
          <LoadingBlock message="Loading OCR rows..." />
        ) : rows.length === 0 ? (
          <Text c="dimmed" size="sm">
            No image uploads yet. Upload an image, then run OCR.
          </Text>
        ) : (
          <ScrollArea type="auto">
            <Table miw={980} highlightOnHover>
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
        <PaginatedTableFooter pagination={pagination} pageIndex={pageIndex} onPageChange={onPageChange} />
      </Stack>

      <Modal
        centered
        onClose={() => setReviewingRow(null)}
        opened={reviewingRow !== null}
        overlayProps={{ backgroundOpacity: 0.74, blur: 3 }}
        padding="lg"
        radius="md"
        scrollAreaComponent={ScrollArea.Autosize}
        shadow="xl"
        size="lg"
        title="Review OCR Text"
      >
        {reviewingRow ? (
          <Stack gap="md">
            <Image alt={reviewingRow.filename} fit="contain" h={260} radius="md" src={imageSrc(reviewingRow)} />
            <Textarea
              autosize
              label="Extracted Text"
              maxRows={8}
              minRows={4}
              onChange={event => {
                if (reviewingSuggestion) {
                  onDraftChange(reviewingSuggestion.id, event.currentTarget.value);
                }
              }}
              readOnly={!reviewingSuggestion}
              value={modalText}
            />
            <Group gap="xs">
              <Badge color={statusColor(reviewingRow)} radius="sm" variant="dot">
                {statusLabel(reviewingRow)}
              </Badge>
              {reviewingRow.confidence !== null ? (
                <Badge color="grape" radius="sm" variant="light">
                  {formatPercent(reviewingRow.confidence)}
                </Badge>
              ) : null}
            </Group>
            <Text c="dimmed" size="sm">
              {reviewingRow.rationale || "Review the literal character extraction."}
            </Text>
            {reviewingSuggestion ? (
              <>
                <Divider />
                <SuggestionActions suggestion={reviewingSuggestion} working={working} onReview={reviewAndClose} />
              </>
            ) : null}
          </Stack>
        ) : null}
      </Modal>
    </PaperPanel>
  );
}
