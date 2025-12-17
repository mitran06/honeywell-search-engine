import { useState } from "react";
import ThreePanelLayout from "@/components/layout/ThreePanelLayout";
import LeftPanelDocuments from "@/components/panels/LeftPanelDocuments";
import RightPanelSearchChat from "@/components/panels/RightPanelSearchChat";
import PdfIframeViewer from "@/components/viewer/PdfIframeViewer";
import { Header } from "@/components/layout/Header";

export function DashboardPage() {
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <Header />

      <div style={{ flex: 1, minHeight: 0, height: "100vh", display: "flex", flexDirection: "column", background: "var(--layout-bg)", }}>
        <ThreePanelLayout
          left={
            <LeftPanelDocuments
              onSelectDocument={(id) => setSelectedDocument(id)}
            />
          }
          center={
            selectedDocument ? (
              <PdfIframeViewer documentId={selectedDocument} />
            ) : (
              <div style={{ padding: 24 }}>
                <h2>Welcome</h2>
                <p>Select a PDF from the left.</p>
              </div>
            )
          }
          right={
            <RightPanelSearchChat
              openDocument={(id) => setSelectedDocument(id)}
            />
          }
        />
      </div>
    </div>
  );
}

export default DashboardPage;
