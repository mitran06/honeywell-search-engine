import React, { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { HiUpload, HiTrash } from "react-icons/hi";
import { documentsApi } from "@/api";
import { formatFileSize, formatRelativeTime } from "@/utils/formatters";
import { FILE_LIMITS } from "@/utils/constants";
import type { Document } from "@/types";
import { Loader } from "@/components/common";

export function LeftPanelDocuments({
  onSelectDocument,
}: {
  onSelectDocument?: (id: string) => void;
}) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await documentsApi.getDocuments();
      setDocuments(res.data.data.documents);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!files.length) return;
      setIsUploading(true);
      setUploadProgress(0);
      try {
        await documentsApi.uploadDocuments(files, p => setUploadProgress(p));
        await fetchDocuments();
      } finally {
        setIsUploading(false);
        setUploadProgress(null);
      }
    },
    [fetchDocuments]
  );

  const { getRootProps, getInputProps } = useDropzone({
    onDrop,
    accept: FILE_LIMITS.ACCEPTED_TYPES,
    maxSize: FILE_LIMITS.MAX_FILE_SIZE,
    disabled: isUploading,
  });

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this PDF?")) return;
    await documentsApi.deleteDocument(id);
    setDocuments(prev => prev.filter(d => d.id !== id));
  };

  return (
    <div style={{ padding: 16, color: "var(--panel-text-primary)" }}>
      {/* Upload Card */}
      <div
        {...getRootProps()}
        style={{
          borderRadius: 14,
          padding: 14,
          marginBottom: 16,
          cursor: "pointer",
          background: "var(--accent-gradient)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              background: "rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <HiUpload size={18} />
          </div>

          <div>
            <div style={{ fontWeight: 600 }}>Upload PDFs</div>
            <div
              style={{
                fontSize: 12,
                color: "var(--panel-text-muted)",
              }}
            >
              Drag & drop or click to browse
            </div>
          </div>
        </div>

        <input {...getInputProps()} />
      </div>

      {/* Upload progress */}
      {isUploading && uploadProgress !== null && (
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              height: 6,
              borderRadius: 6,
              background: "var(--panel-border)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${uploadProgress}%`,
                background: "#22c55e",
                transition: "width 0.2s",
              }}
            />
          </div>
        </div>
      )}

      {/* Header  */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <h3 style={{ margin: 0, fontSize: 15 }}>Your PDFs</h3>
        <button
          onClick={async () => {
            if (!confirm("Delete all PDFs?")) return;
            await documentsApi.deleteAllDocuments();
            setDocuments([]);
          }}
          style={{
            background: "none",
            border: "none",
            color: "var(--danger)",
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          Clear All
        </button>
      </div>

      {/* List*/}
      {isLoading ? (
        <Loader text="Loading..." />
      ) : documents.length === 0 ? (
        <p style={{ color: "var(--panel-text-muted)" }}>
          No documents uploaded
        </p>
      ) : (
        documents.map(doc => (
          <div
            key={doc.id}
            style={{
              background: "var(--accent-gradient)",
              borderRadius: 14,
              padding: 14,
              marginBottom: 10,
              display: "flex",
              gap: 12,
              boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
            }}
          >
            {/* Document info */}
            <div
              onClick={() => onSelectDocument?.(doc.id)}
              style={{
                cursor: "pointer",
                flex: 1,
                minWidth: 0, // CRITICAL for overflow fix
              }}
            >
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 14,
                  lineHeight: 1.4,
                  marginBottom: 6,

                  /* OVERFLOW FIX — SAME AS ORIGINAL LOGIC */
                  whiteSpace: "normal",
                  wordBreak: "break-word",
                }}
              >
                {doc.filename}
              </div>

              <div
                style={{
                  fontSize: 12,
                  color: "var(--panel-text-muted)",
                }}
              >
                {formatFileSize(doc.file_size)} •{" "}
                {formatRelativeTime(doc.created_at)}
              </div>
            </div>

            {/* Delete */}
            <button
              onClick={() => handleDelete(doc.id)}
              style={{
                background: "none",
                border: "none",
                color: "var(--danger)",
                cursor: "pointer",
                alignSelf: "flex-start",
              }}
            >
              <HiTrash size={18} />
            </button>
          </div>
        ))
      )}
    </div>
  );
}

export default LeftPanelDocuments;
