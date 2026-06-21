import { Box, Paper, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";

import { UI } from "@/lib/constants";

export function CompactPanel({ title, eyebrow, children }: { title: string; eyebrow: string; children: ReactNode }) {
  return (
    <Paper withBorder radius="md" p="md" h="100%" style={{ background: UI.panel, borderColor: UI.border }}>
      <Stack gap="sm" h="100%">
        <Box>
          <Text c="dimmed" fw={700} size="xs" tt="uppercase">
            {eyebrow}
          </Text>
          <Title order={3} size="h4">
            {title}
          </Title>
        </Box>
        {children}
      </Stack>
    </Paper>
  );
}
