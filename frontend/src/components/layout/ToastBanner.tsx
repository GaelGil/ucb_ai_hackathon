import { Button, Group, Paper, Text } from "@mantine/core";

import { UI } from "@/lib/constants";
import type { Toast } from "@/types/domain";

export function ToastBanner({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  return (
    <Paper
      aria-live="polite"
      withBorder
      p="sm"
      radius="md"
      style={{ background: UI.panelSoft, borderColor: `var(--mantine-color-${toast.tone}-6)` }}
    >
      <Group justify="space-between">
        <Text size="sm">{toast.message}</Text>
        <Button color="violet" size="compact-xs" variant="subtle" onClick={onDismiss}>
          Dismiss
        </Button>
      </Group>
    </Paper>
  );
}
