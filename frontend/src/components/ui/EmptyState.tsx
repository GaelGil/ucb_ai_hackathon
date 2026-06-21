import { Paper, Stack, Text, Title } from "@mantine/core";

import { UI } from "@/lib/constants";

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <Paper withBorder radius="md" p="lg" style={{ background: UI.panel, borderColor: UI.border }}>
      <Stack gap={4}>
        <Title order={3} size="h4">
          {title}
        </Title>
        <Text c="dimmed" size="sm">
          {message}
        </Text>
      </Stack>
    </Paper>
  );
}
