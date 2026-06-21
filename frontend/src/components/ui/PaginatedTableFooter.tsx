import { ActionIcon, Group, Text } from "@mantine/core";
import { TbChevronLeft, TbChevronRight } from "react-icons/tb";

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
  const currentPage = Math.min(Math.max(pageIndex, 0), pageCount - 1);
  const start = Math.min(currentPage * limit + 1, pagination.total);
  const end = Math.min((currentPage + 1) * limit, pagination.total);
  const canGoPrevious = currentPage > 0;
  const canGoNext = currentPage < pageCount - 1;

  return (
    <Group justify="space-between" wrap="wrap">
      <Text c="dimmed" size="sm">
        Showing {start}-{end} of {pagination.total}
      </Text>
      {pageCount > 1 ? (
        <Group gap="xs">
          <ActionIcon
            aria-label="Previous page"
            color="gray"
            disabled={!canGoPrevious}
            onClick={() => onPageChange(currentPage - 1)}
            radius="md"
            size="sm"
            variant="subtle"
          >
            <TbChevronLeft aria-hidden="true" size={16} />
          </ActionIcon>
          <Text c="dimmed" size="sm">
            Page {currentPage + 1} of {pageCount}
          </Text>
          <ActionIcon
            aria-label="Next page"
            color="gray"
            disabled={!canGoNext}
            onClick={() => onPageChange(currentPage + 1)}
            radius="md"
            size="sm"
            variant="subtle"
          >
            <TbChevronRight aria-hidden="true" size={16} />
          </ActionIcon>
        </Group>
      ) : null}
    </Group>
  );
}
