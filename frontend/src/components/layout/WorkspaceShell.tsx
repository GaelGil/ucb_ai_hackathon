import { AppShell, Box, Group, Stack, Title } from "@mantine/core";
import type { ReactNode } from "react";

import { SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH, UI } from "@/lib/constants";
import type { Dataset } from "@/types/domain";

export function WorkspaceShell({
  selectedDataset,
  sidebar,
  sidebarCollapsed,
  children,
}: {
  selectedDataset: Dataset | null;
  sidebar: ReactNode;
  sidebarCollapsed: boolean;
  children: ReactNode;
}) {
  return (
    <AppShell
      layout="alt"
      header={{ height: 64 }}
      navbar={{
        width: sidebarCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH,
        breakpoint: "sm",
        collapsed: { mobile: false },
      }}
      padding={0}
    >
      <AppShell.Header
        style={{
          background: UI.header,
          borderBottom: `1px solid ${UI.border}`,
        }}
      >
        <Group h="100%" px="md" wrap="nowrap">
          <Title order={1} size="h3" lh={1.1} lineClamp={1}>
            {selectedDataset?.language_name ?? "Language"}
          </Title>
        </Group>
      </AppShell.Header>

      {sidebar}

      <AppShell.Main style={{ background: UI.background, minHeight: "100vh" }}>
        <Box id="workspace-main" w="100%" maw={1480} mx="auto" px={{ base: "sm", sm: "lg" }} py="lg">
          <Stack gap="lg">{children}</Stack>
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}
