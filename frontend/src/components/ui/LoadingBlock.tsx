import { Group, Loader, Text } from "@mantine/core";

export function LoadingBlock({ message = "Loading data…" }: { message?: string }) {
  return (
    <Group gap="sm" py="lg">
      <Loader color="violet" size="sm" />
      <Text c="dimmed" size="sm">
        {message}
      </Text>
    </Group>
  );
}
