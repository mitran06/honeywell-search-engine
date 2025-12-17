import { useEffect, useState } from "react";
import { documentsApi } from "@/api";
import { Loader } from "@/components/common";

interface Props {
  documentId: string;
}

export default function PdfIframeViewer({ documentId }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        setError(null);

        const blob = await documentsApi.getDocumentFile(documentId);
        if (!active) return;

        const objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      } catch (e) {
        console.error(e);
        setError("Failed to load PDF");
      }
    };

    load();

    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentId]);

  if (error) {
    return <div style={{ padding: 24, color: "red" }}>{error}</div>;
  }

  if (!url) {
    return <Loader size="lg" text="Loading PDF..." />;
  }

  return (
    <iframe
      src={url}
      title="PDF Viewer"
      style={{
        width: "100%",
        height: "100%",
        border: "none",
        background: "#1e1e1e",
      }}
    />
  );
}
