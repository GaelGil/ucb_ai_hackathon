import {
  ActionIcon,
  AppShell,
  Box,
  Button,
  Divider,
  Group,
  Loader,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Tooltip,
} from "@mantine/core";
import { TbLayoutSidebarLeftCollapse, TbPlus, TbTrash } from "react-icons/tb";

import { UI } from "@/lib/constants";
import type { Dataset } from "@/types/domain";

export function Sidebar({
  addLanguageFormOpen,
  datasetName,
  datasets,
  datasetsLoading,
  languageCode,
  languageName,
  selectedDataset,
  sidebarCollapsed,
  working,
  onCreateDataset,
  onDatasetNameChange,
  onLanguageCodeChange,
  onLanguageNameChange,
  onSelectDataset,
  onSetAddLanguageFormOpen,
  onSetDeleteTarget,
  onSetSidebarCollapsed,
}: {
  addLanguageFormOpen: boolean;
  datasetName: string;
  datasets: Dataset[];
  datasetsLoading: boolean;
  languageCode: string;
  languageName: string;
  selectedDataset: Dataset | null;
  sidebarCollapsed: boolean;
  working: boolean;
  onCreateDataset: () => void;
  onDatasetNameChange: (value: string) => void;
  onLanguageCodeChange: (value: string) => void;
  onLanguageNameChange: (value: string) => void;
  onSelectDataset: (datasetId: string) => void;
  onSetAddLanguageFormOpen: (value: boolean | ((current: boolean) => boolean)) => void;
  onSetDeleteTarget: (dataset: Dataset) => void;
  onSetSidebarCollapsed: (value: boolean) => void;
}) {
  return (
    <AppShell.Navbar
      style={{
        background: UI.navbar,
        borderRight: `1px solid ${UI.border}`,
      }}
    >
      <Stack gap="sm" h="100%" p="sm">
        {sidebarCollapsed ? (
          <Stack align="center" gap="sm" py="xs">
            <Tooltip label="Expand Sidebar" position="right">
              <ActionIcon
                aria-label="Expand sidebar"
                color="violet"
                onClick={() => onSetSidebarCollapsed(false)}
                radius="md"
                size={46}
                variant="filled"
              >
                <Text fw={850} size="sm">
                  LB
                </Text>
              </ActionIcon>
            </Tooltip>
          </Stack>
        ) : (
          <Group justify="space-between" wrap="nowrap" py="xs">
            <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
              <ThemeIcon color="violet" radius="md" size={42} variant="filled">
                LB
              </ThemeIcon>
              <Box style={{ minWidth: 0 }}>
                <Text fw={850} lh={1} size="lg" truncate="end">
                  LangBase
                </Text>
                <Text c="dimmed" size="xs" truncate="end">
                  Low-resource AI workspace
                </Text>
              </Box>
            </Group>
            <Tooltip label="Collapse Sidebar">
              <ActionIcon
                aria-label="Collapse sidebar"
                color="gray"
                onClick={() => onSetSidebarCollapsed(true)}
                size={38}
                variant="subtle"
              >
                <TbLayoutSidebarLeftCollapse aria-hidden="true" size={20} />
              </ActionIcon>
            </Tooltip>
          </Group>
        )}

        <ScrollArea flex={1} type="hover">
          <Stack align={sidebarCollapsed ? "center" : "stretch"} gap={6}>
            {!sidebarCollapsed ? (
              <Box px="xs" py={4}>
                <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                  Languages
                </Text>
              </Box>
            ) : null}
            {datasetsLoading ? (
              sidebarCollapsed ? (
                <ActionIcon aria-label="Loading languages" disabled radius="md" size={46} variant="subtle">
                  <Loader color="violet" size="xs" />
                </ActionIcon>
              ) : (
                <Group gap="xs" px="xs" py="sm">
                  <Loader color="violet" size="xs" />
                  <Text c="dimmed" size="sm">
                    Loading languages…
                  </Text>
                </Group>
              )
            ) : datasets.length === 0 ? (
              <Text c="dimmed" px={sidebarCollapsed ? 0 : "xs"} size="sm" ta={sidebarCollapsed ? "center" : "left"}>
                {sidebarCollapsed ? "None" : "No languages yet."}
              </Text>
            ) : (
              datasets.map(dataset =>
                sidebarCollapsed ? (
                  <Tooltip
                    key={dataset.id}
                    label={`${dataset.language_name} · ${dataset.name}`}
                    position="right"
                  >
                    <ActionIcon
                      aria-label={`Select ${dataset.language_name}`}
                      color={dataset.id === selectedDataset?.id ? "green" : "gray"}
                      onClick={() => onSelectDataset(dataset.id)}
                      radius="md"
                      size={46}
                      variant={dataset.id === selectedDataset?.id ? "filled" : "light"}
                    >
                      <Text fw={800} size="xs">
                        {dataset.language_code.slice(0, 2).toUpperCase()}
                      </Text>
                    </ActionIcon>
                  </Tooltip>
                ) : (
                  <Group
                    key={dataset.id}
                    align="stretch"
                    gap={6}
                    wrap="nowrap"
                  >
                    <Button
                      color={dataset.id === selectedDataset?.id ? "green" : "gray"}
                      fullWidth
                      justify="flex-start"
                      leftSection={
                        <ThemeIcon
                          color={dataset.id === selectedDataset?.id ? "green" : "violet"}
                          radius="md"
                          size={34}
                          variant={dataset.id === selectedDataset?.id ? "filled" : "light"}
                        >
                          {dataset.language_code.slice(0, 2).toUpperCase()}
                        </ThemeIcon>
                      }
                      onClick={() => onSelectDataset(dataset.id)}
                      style={{ flex: 1, height: "auto", minWidth: 0, paddingBottom: 8, paddingTop: 8 }}
                      variant={dataset.id === selectedDataset?.id ? "light" : "subtle"}
                    >
                      <Box style={{ minWidth: 0, textAlign: "left" }}>
                        <Text fw={700} size="sm" truncate="end">
                          {dataset.name}
                        </Text>
                        <Text c="dimmed" size="xs" truncate="end">
                          {dataset.language_name} · {dataset.language_code}
                        </Text>
                      </Box>
                    </Button>
                    <Tooltip label={`Delete ${dataset.language_name}`}>
                      <ActionIcon
                        aria-label={`Delete ${dataset.language_name}`}
                        color="red"
                        disabled={working}
                        onClick={() => onSetDeleteTarget(dataset)}
                        radius="md"
                        size={42}
                        variant="subtle"
                      >
                        <TbTrash aria-hidden="true" size={18} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                ),
              )
            )}
          </Stack>
        </ScrollArea>

        {!sidebarCollapsed ? (
          <>
            <Divider />
            <Group justify="space-between" wrap="nowrap">
              <Text c="dimmed" fw={700} size="xs" tt="uppercase">
                New Language
              </Text>
              <Button
                color="gray"
                onClick={() => onSetAddLanguageFormOpen(current => !current)}
                size="compact-xs"
                type="button"
                variant="subtle"
              >
                {addLanguageFormOpen ? "Hide Form" : "Show Form"}
              </Button>
            </Group>
            {addLanguageFormOpen ? (
              <Box
                component="form"
                onSubmit={event => {
                  event.preventDefault();
                  onCreateDataset();
                }}
              >
                <Stack gap="xs">
                  <TextInput
                    autoComplete="off"
                    label="Dataset"
                    name="datasetName"
                    onChange={event => onDatasetNameChange(event.currentTarget.value)}
                    placeholder="Dataset name"
                    size="xs"
                    value={datasetName}
                  />
                  <Group grow>
                    <TextInput
                      autoComplete="off"
                      label="Code"
                      name="languageCode"
                      onChange={event => onLanguageCodeChange(event.currentTarget.value)}
                      placeholder="Language code"
                      size="xs"
                      spellCheck={false}
                      value={languageCode}
                    />
                    <TextInput
                      autoComplete="off"
                      label="Language"
                      name="languageName"
                      onChange={event => onLanguageNameChange(event.currentTarget.value)}
                      placeholder="Language name"
                      size="xs"
                      value={languageName}
                    />
                  </Group>
                  <Button
                    color="green"
                    disabled={working || !datasetName.trim() || !languageCode.trim() || !languageName.trim()}
                    leftSection={<TbPlus aria-hidden="true" size={15} />}
                    size="xs"
                    type="submit"
                  >
                    Create Language
                  </Button>
                </Stack>
              </Box>
            ) : null}
          </>
        ) : null}
      </Stack>
    </AppShell.Navbar>
  );
}
