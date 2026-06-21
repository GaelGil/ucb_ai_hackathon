import { Badge, Box, Button, Card, Group, Stack, Text, ThemeIcon, Title } from "@mantine/core";

import { UI } from "@/lib/constants";

export function ModelTrainingCard({
  actionLabel,
  description,
  disabled,
  onAction,
  status,
  title,
  tone,
}: {
  actionLabel: string;
  description: string;
  disabled?: boolean;
  onAction?: () => void;
  status: string;
  title: string;
  tone: string;
}) {
  return (
    <Card withBorder radius="md" p="lg" style={{ background: UI.panel, borderColor: UI.border }}>
      <Stack gap="md" h="100%">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Box>
            <Text c="dimmed" fw={700} size="xs" tt="uppercase">
              Model
            </Text>
            <Title order={3} size="h3">
              {title}
            </Title>
          </Box>
          <ThemeIcon color={tone} radius="md" variant="light">
            {title.slice(0, 2)}
          </ThemeIcon>
        </Group>
        <Text c="dimmed" size="sm">
          {description}
        </Text>
        <Badge color={tone} radius="sm" variant="light" w="fit-content">
          {status}
        </Badge>
        <Button color={tone} disabled={disabled} mt="auto" onClick={onAction} variant="light">
          {actionLabel}
        </Button>
      </Stack>
    </Card>
  );
}
