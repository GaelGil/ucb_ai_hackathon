import { Box, Modal, ScrollArea, Stack, Text } from "@mantine/core";

import type { DetailContent } from "@/types/domain";

export function DetailModal({
  selectedDetail,
  onClose,
}: {
  selectedDetail: DetailContent | null;
  onClose: () => void;
}) {
  return (
    <Modal
      centered
      onClose={onClose}
      opened={selectedDetail !== null}
      scrollAreaComponent={ScrollArea.Autosize}
      size="lg"
      title={selectedDetail?.title ?? "Details"}
    >
      <Stack gap="md">
        {selectedDetail?.rows.map(row => (
          <Box key={row.label}>
            <Text c="dimmed" fw={700} size="xs" tt="uppercase">
              {row.label}
            </Text>
            {typeof row.value === "string" || typeof row.value === "number" ? (
              <Text size="sm" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {row.value}
              </Text>
            ) : (
              row.value
            )}
          </Box>
        ))}
      </Stack>
    </Modal>
  );
}
