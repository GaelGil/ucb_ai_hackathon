import { Group, Pagination, Text } from "@mantine/core";

import { PAGE_SIZE } from "@/lib/constants";
import type { PaginationMeta } from "@/types/domain";

export function PaginatedTableFooter({
  pagination,
  pageIndex,
  onPageChange,
}: {
  pagination: PaginationMeta;
  pageIndex: number;
  onPageChange: (pageIndex: number) => void;
}) {
  if (pagination.total <= 0) {
    return null;
  }

  const limit = Math.max(pagination.limit || PAGE_SIZE, 1);
  const pageCount = Math.max(1, Math.ceil(pagination.total / limit));
  const start = Math.min(pagination.offset + 1, pagination.total);
  const end = Math.min(pagination.offset + limit, pagination.total);

  return (
    <Group justify="space-between" wrap="wrap">
      <Text c="dimmed" size="sm">
        Showing {start}-{end} of {pagination.total}
      </Text>
      {pageCount > 1 ? (
        <Pagination
          color="violet"
          onChange={value => onPageChange(value - 1)}
          radius="md"
          size="sm"
          total={pageCount}
          value={Math.min(pageIndex + 1, pageCount)}
        />
      ) : null}
    </Group>
  );
}
