import { Grid, Paper, Tabs } from "@mantine/core";
import {
  TbDatabase,
  TbFileText,
  TbTags,
  TbUpload,
  TbWand,
} from "react-icons/tb";

import { DeleteDatasetModal } from "@/components/layout/DeleteDatasetModal";
import { DetailModal } from "@/components/layout/DetailModal";
import { Sidebar } from "@/components/layout/Sidebar";
import { ToastBanner } from "@/components/layout/ToastBanner";
import { WorkspaceShell } from "@/components/layout/WorkspaceShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingBlock } from "@/components/ui/LoadingBlock";
import { UI } from "@/lib/constants";
import { useWorkspaceController } from "@/hooks/useWorkspaceController";
import { JobsPanel } from "@/features/jobs/JobsPanel";
import { OcrSuggestionsTable } from "@/features/labels/OcrSuggestionsTable";
import { PosSuggestionsTable } from "@/features/labels/PosSuggestionsTable";
import { TranslationTable } from "@/features/labels/TranslationTable";
import { ModelsPanel } from "@/features/models/ModelsPanel";
import { ResearchPanel } from "@/features/research/ResearchPanel";
import { UploadTab } from "@/features/upload/UploadTab";

export function App() {
  const workspace = useWorkspaceController();

  return (
    <>
      <DeleteDatasetModal
        deleteTarget={workspace.deleteTarget}
        working={workspace.working}
        onClose={() => workspace.setDeleteTarget(null)}
        onDelete={dataset => void workspace.deleteDataset(dataset)}
      />
      <DetailModal selectedDetail={workspace.selectedDetail} onClose={() => workspace.setSelectedDetail(null)} />

      <WorkspaceShell
        selectedDataset={workspace.selectedDataset}
        sidebarCollapsed={workspace.sidebarCollapsed}
        sidebar={
          <Sidebar
            addLanguageFormOpen={workspace.addLanguageFormOpen}
            datasetName={workspace.datasetName}
            datasets={workspace.datasets}
            datasetsLoading={workspace.datasetsLoading}
            languageCode={workspace.languageCode}
            languageName={workspace.languageName}
            selectedDataset={workspace.selectedDataset}
            sidebarCollapsed={workspace.sidebarCollapsed}
            working={workspace.working}
            onCreateDataset={() => void workspace.createDataset()}
            onDatasetNameChange={workspace.setDatasetName}
            onLanguageCodeChange={workspace.setLanguageCode}
            onLanguageNameChange={workspace.setLanguageName}
            onSelectDataset={workspace.setSelectedDatasetId}
            onSetAddLanguageFormOpen={workspace.setAddLanguageFormOpen}
            onSetDeleteTarget={workspace.setDeleteTarget}
            onSetSidebarCollapsed={workspace.setSidebarCollapsed}
          />
        }
      >
        {workspace.toast ? (
          <ToastBanner toast={workspace.toast} onDismiss={() => workspace.setToast(null)} />
        ) : null}

        {workspace.selectedDataset ? (
          <>
            {workspace.activeTab === "pos" || workspace.activeTab === "translate" ? (
              <Grid gutter="md">
                <Grid.Col span={{ base: 12, lg: 8 }}>
                  <ResearchPanel
                    activeType={workspace.activeResearchType}
                    research={workspace.researchByType[workspace.activeResearchType]}
                    working={workspace.working}
                    onOpenDetail={workspace.openDetail}
                    onResearch={() => void workspace.runResearch(false)}
                    onRefreshResearch={() => void workspace.runResearch(true)}
                    onTypeChange={workspace.setActiveResearchType}
                  />
                </Grid.Col>
                <Grid.Col span={{ base: 12, lg: 4 }}>
                  <JobsPanel jobs={workspace.jobs} />
                </Grid.Col>
              </Grid>
            ) : null}
            <Tabs value={workspace.activeTab} onChange={workspace.handleTabChange} radius="md" variant="pills">
              <Tabs.List>
                <Tabs.Tab leftSection={<TbTags aria-hidden="true" size={16} />} value="pos">
                  POS
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbWand aria-hidden="true" size={16} />} value="ocr">
                  OCR
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbFileText aria-hidden="true" size={16} />} value="translate">
                  Translate
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbUpload aria-hidden="true" size={16} />} value="upload">
                  Upload
                </Tabs.Tab>
                <Tabs.Tab leftSection={<TbDatabase aria-hidden="true" size={16} />} value="models">
                  Models
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="pos" pt="md">
                <PosSuggestionsTable
                  suggestions={workspace.suggestions}
                  tokenDrafts={workspace.tokenDrafts}
                  pagination={workspace.workspaceData.posSuggestionsPage}
                  pageIndex={workspace.posSuggestionsPage}
                  loading={workspace.workspaceLoading}
                  working={workspace.working}
                  onGenerate={() => void workspace.generatePosSuggestions()}
                  onOpenDetail={workspace.openDetail}
                  onPageChange={workspace.setPosSuggestionsPage}
                  onReview={(suggestion, action) => void workspace.reviewSuggestion(suggestion, action)}
                  onTokenChange={workspace.updateTokenDraft}
                />
              </Tabs.Panel>

              <Tabs.Panel value="ocr" pt="md">
                <OcrSuggestionsTable
                  latestAssetImport={workspace.latestAssetImport}
                  imageImports={workspace.imageAssetImports}
                  selectedImportIds={workspace.selectedOcrImportIds}
                  suggestions={workspace.ocrSuggestions}
                  drafts={workspace.ocrDrafts}
                  pagination={workspace.workspaceData.ocrSuggestionsPage}
                  pageIndex={workspace.ocrSuggestionsPage}
                  loading={workspace.workspaceLoading}
                  working={workspace.working}
                  onOpenDetail={workspace.openDetail}
                  onPageChange={workspace.setOcrSuggestionsPage}
                  onRunOcr={() => void workspace.runOcr()}
                  onSelectedImportIdsChange={workspace.setSelectedOcrImportIds}
                  onDraftChange={(id, value) => workspace.setOcrDrafts(previous => ({ ...previous, [id]: value }))}
                  onReview={(suggestion, action) => void workspace.reviewSuggestion(suggestion, action)}
                />
              </Tabs.Panel>

              <Tabs.Panel value="translate" pt="md">
                <TranslationTable
                  labels={workspace.translationLabels}
                  drafts={workspace.translationDrafts}
                  labelsPagination={workspace.workspaceData.translationLabelsPage}
                  labelsPageIndex={workspace.translationLabelsPage}
                  pendingSuggestionTotal={workspace.dashboard?.suggestion_counts.translation ?? 0}
                  research={workspace.researchByType.translation}
                  loading={workspace.workspaceLoading}
                  working={workspace.working}
                  onGenerate={() => void workspace.generateTranslationSuggestions()}
                  onOpenDetail={workspace.openDetail}
                  onLabelsPageChange={workspace.setTranslationLabelsPage}
                  onDraftChange={(id, value) => workspace.setTranslationDrafts(previous => ({ ...previous, [id]: value }))}
                  onReview={(suggestion, action) => void workspace.reviewSuggestion(suggestion, action)}
                />
              </Tabs.Panel>

              <Tabs.Panel value="upload" pt="md">
                <UploadTab
                  manualSource={workspace.manualSource}
                  manualImportKind={workspace.manualImportKind}
                  manualText={workspace.manualText}
                  fileImportKind={workspace.fileImportKind}
                  uploadFile={workspace.uploadFile}
                  uploadFileIsCsv={workspace.uploadFileIsCsv}
                  imports={workspace.dashboard?.imports ?? []}
                  loading={workspace.workspaceLoading}
                  working={workspace.working}
                  onManualSourceChange={workspace.setManualSource}
                  onManualImportKindChange={workspace.setManualImportKind}
                  onManualTextChange={workspace.setManualText}
                  onFileImportKindChange={workspace.setFileImportKind}
                  onUploadFileChange={workspace.setUploadFile}
                  onManualImport={() => void workspace.importManualText()}
                  onFileImport={() => void workspace.importFile()}
                />
              </Tabs.Panel>

              <Tabs.Panel value="models" pt="md">
                <ModelsPanel
                  acceptedPosCount={workspace.acceptedPosCount}
                  posModel={workspace.dashboard?.pos_model ?? null}
                  working={workspace.working}
                  onTrainPos={() => void workspace.trainPosModel()}
                />
              </Tabs.Panel>
            </Tabs>
          </>
        ) : workspace.datasetsLoading ? (
          <Paper withBorder radius="md" p="lg" style={{ background: UI.panel, borderColor: UI.border }}>
            <LoadingBlock message="Loading workspace data…" />
          </Paper>
        ) : (
          <EmptyState
            title="No backend data yet"
            message="Create a language from the sidebar or import data once a language exists."
          />
        )}
      </WorkspaceShell>
    </>
  );
}

export default App;
