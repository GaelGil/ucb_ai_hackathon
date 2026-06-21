import { Button, Text } from "@mantine/core";

export function PreviewTextButton({
  text,
  title,
  onOpen,
  fw = 700,
}: {
  text: string | null | undefined;
  title: string;
  onOpen: () => void;
  fw?: number;
}) {
  const value = text?.trim() || "No text";
  return (
    <Button
      aria-label={`View ${title}`}
      color="gray"
      h="auto"
      justify="start"
      onClick={onOpen}
      p={0}
      radius="sm"
      variant="subtle"
      w="100%"
      styles={{
        inner: { justifyContent: "flex-start", minWidth: 0 },
        label: { minWidth: 0, whiteSpace: "normal", width: "100%" },
      }}
    >
      <Text fw={fw} lineClamp={2} size="sm" style={{ minWidth: 0, overflowWrap: "anywhere", textAlign: "left" }}>
        {value}
      </Text>
    </Button>
  );
}
