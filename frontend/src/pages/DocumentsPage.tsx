import {
  ArrowDownToLine,
  FileImage,
  FilePlus2,
  FileText,
  FileUp,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import {
  api,
  downloadDocument,
  type DocumentRecord,
} from "../api";
import { useVehicle } from "../components/AppShell";
import {
  EmptyState,
  ErrorBanner,
  formatDate,
  LoadingState,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components/Shared";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "Size not available";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function safeDownloadName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, "_");
}

export function DocumentsPage() {
  const { activeVehicle } = useVehicle();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentType, setDocumentType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async () => {
    const vehicleId = activeVehicle?.id;
    if (!vehicleId) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setDocuments(
        await api<DocumentRecord[]>(
          `/vehicles/${vehicleId}/documents?skip=0&limit=100`,
        ),
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not load documents",
      );
    } finally {
      setLoading(false);
    }
  }, [activeVehicle?.id]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeVehicle || !file) {
      setError("Choose a file before uploading.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", file);
      if (documentType) body.append("document_type", documentType);
      await api<DocumentRecord>(
        `/vehicles/${activeVehicle.id}/documents`,
        { method: "POST", body },
      );
      setFile(null);
      setDocumentType("");
      if (fileInput.current) fileInput.current.value = "";
      await loadDocuments();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not upload file");
    } finally {
      setUploading(false);
    }
  }

  async function download(document: DocumentRecord) {
    setError("");
    try {
      const blob = await downloadDocument(document.id);
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = safeDownloadName(document.file_name);
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not download file",
      );
    }
  }

  async function deleteDocument(document: DocumentRecord) {
    if (!window.confirm(`Delete “${document.file_name}”?`)) return;
    setError("");
    try {
      await api<void>(`/documents/${document.id}`, { method: "DELETE" });
      await loadDocuments();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete document");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={activeVehicle?.vehicle_name ?? "YOUR FILES"}
        title="The paperwork, without the pile."
        description="Keep invoices, receipts, and vehicle documents close to their vehicle. Invoice files may be processed in the background."
      />
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <section className="dashboard-grid document-grid">
        <Panel title="Add a document" subtitle="PDF, JPG, JPEG, or PNG · up to 10 MB">
          {!activeVehicle ? (
            <EmptyState
              icon={FileText}
              title="Select a vehicle first"
              description="Documents stay organized by vehicle."
            />
          ) : (
            <form className="form-stack" onSubmit={upload}>
              <button
                type="button"
                className={`upload-dropzone ${file ? "has-file" : ""}`}
                onClick={() => fileInput.current?.click()}
              >
                <span className="upload-icon"><FileUp size={21} /></span>
                <strong>{file ? file.name : "Choose a file to upload"}</strong>
                <small>
                  {file ? formatBytes(file.size) : "Browse from your device"}
                </small>
              </button>
              <input
                ref={fileInput}
                className="visually-hidden"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                onChange={(event) =>
                  setFile(event.target.files?.[0] ?? null)
                }
              />
              <label className="field">
                <span>Document type</span>
                <select
                  value={documentType}
                  onChange={(event) => setDocumentType(event.target.value)}
                >
                  <option value="">Choose a type (optional)</option>
                  <option value="invoice">Invoice</option>
                  <option value="receipt">Receipt</option>
                  <option value="bill">Bill</option>
                  <option value="insurance">Insurance</option>
                  <option value="registration">Registration</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <button
                className="button primary wide"
                disabled={!file || uploading}
              >
                {uploading ? "Uploading..." : "Upload document"}
                <FilePlus2 size={16} />
              </button>
              <p className="form-note">
                Invoice text may be sent to the configured AI provider for
                extraction. Avoid uploading documents you do not want processed.
              </p>
            </form>
          )}
        </Panel>

        <Panel
          title="Vehicle documents"
          subtitle={
            activeVehicle
              ? `Files for ${activeVehicle.vehicle_name}`
              : "Select a vehicle to view files"
          }
        >
          {loading ? (
            <LoadingState label="Loading your documents..." />
          ) : documents.length ? (
            <div className="document-list">
              {documents.map((document) => {
                const isImage = document.file_type.startsWith("image/");
                return (
                  <article className="document-row" key={document.id}>
                    <span className="document-icon">
                      {isImage ? <FileImage size={20} /> : <FileText size={20} />}
                    </span>
                    <div className="document-copy">
                      <strong title={document.file_name}>{document.file_name}</strong>
                      <small>
                        {document.document_type || "Uncategorized"} ·{" "}
                        {formatBytes(document.file_size)} ·{" "}
                        {formatDate(document.uploaded_at)}
                      </small>
                      <div className="document-status">
                        <StatusBadge status={document.processing_status} />
                      </div>
                    </div>
                    <div className="document-actions">
                      <button
                        className="icon-button"
                        aria-label={`Download ${document.file_name}`}
                        onClick={() => void download(document)}
                      >
                        <ArrowDownToLine size={16} />
                      </button>
                      <button
                        className="icon-button danger-hover"
                        aria-label={`Delete ${document.file_name}`}
                        onClick={() => void deleteDocument(document)}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <EmptyState
              icon={FileText}
              title="Your document shelf is empty"
              description="Add an invoice or vehicle document to keep it connected to this vehicle."
            />
          )}
        </Panel>
      </section>
    </div>
  );
}
