import { Badge, ScrollArea, Table, Text } from "@mantine/core";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useMemo } from "react";

import { LoadingBlock } from "@/components/ui/LoadingBlock";
import { sourceColor, statusColor } from "@/lib/format";
import type { ImportRecord } from "@/types/domain";

export function ImportsTable({ imports, loading = false }: { imports: ImportRecord[]; loading?: boolean }) {
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
