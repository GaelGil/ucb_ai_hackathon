import { Button, Group, Modal, Stack, Text } from "@mantine/core";
import { TbTrash } from "react-icons/tb";

import type { Dataset } from "@/types/domain";

export function DeleteDatasetModal({
  deleteTarget,
  working,
  onClose,
  onDelete,
}: {
  deleteTarget: Dataset | null;
  working: boolean;
  onClose: () => void;
  onDelete: (dataset: Dataset) => void;
}) {
  return (
    <Modal centered onClose={onClose} opened={deleteTarget !== null} title="Delete Language">
      <Stack gap="md">
        <Text c="dimmed" size="sm">
          Delete {deleteTarget?.language_name ?? "this language"} and remove its imports, labels, research, jobs,
          and model state.
        </Text>
        <Group justify="flex-end">
          <Button color="gray" disabled={working} onClick={onClose} variant="subtle">
            Cancel
          </Button>
          <Button
            color="red"
            disabled={working || !deleteTarget}
            leftSection={<TbTrash aria-hidden="true" size={16} />}
            onClick={() => {
              if (deleteTarget) {
                onDelete(deleteTarget);
              }
            }}
          >
            Delete Language
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
