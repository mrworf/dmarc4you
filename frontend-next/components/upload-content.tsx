"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { apiClient, ApiError } from "@/lib/api/client";
import type { ReportsIngestBody, ReportsIngestResponse } from "@/lib/api/types";

export function UploadContent() {
  const [textValue, setTextValue] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [submittedJobId, setSubmittedJobId] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: (body: ReportsIngestBody) => apiClient.post<ReportsIngestResponse>("/api/v1/reports/ingest", body),
    onSuccess: (data) => {
      setSubmittedJobId(data.job_id);
      setTextValue("");
      setFiles([]);
    },
  });

  async function handleSubmit() {
    setSubmittedJobId(null);

    if (textValue.trim() && files.length) {
      return;
    }

    if (!textValue.trim() && !files.length) {
      return;
    }

    let reports: ReportsIngestBody["reports"] = [];

    if (files.length) {
      reports = await Promise.all(
        files.map(async (file) => {
          const bytes = new Uint8Array(await file.arrayBuffer());
          return {
            content_type: file.name.endsWith(".eml") ? "message/rfc822" : "application/xml",
            content_encoding: isGzipFile(file.name, bytes) ? "gzip" : "none",
            content_transfer_encoding: "base64",
            content: arrayBufferToBase64(bytes),
          };
        }),
      );
    } else {
      reports = [
        {
          content_type: "application/xml",
          content_encoding: "none",
          content_transfer_encoding: "base64",
          content: utf8ToBase64(textValue.trim()),
        },
      ];
    }

    await uploadMutation.mutateAsync({
      source: "web",
      reports,
    });
  }

  const mutationError = uploadMutation.error instanceof ApiError ? uploadMutation.error.message : null;
  const showMixedInputError = Boolean(textValue.trim() && files.length);
  const showMissingInputError = Boolean(!textValue.trim() && !files.length && uploadMutation.isError);

  return (
    <AppShell
      title="Upload"
      description="Submit DMARC report files or pasted XML and jump straight to the resulting ingest job."
      actions={
        <button
          className="button-secondary"
          onClick={() => {
            setTextValue("");
            setFiles([]);
            setSubmittedJobId(null);
          }}
          type="button"
        >
          Reset
        </button>
      }
    >
      <section className="surface-card stack">
        <div>
          <h2 style={{ margin: "0 0 8px" }}>Paste XML or upload report files</h2>
          <p className="status-text">
            Use either pasted XML or one or more files. Compressed files and `.eml` attachments are supported.
          </p>
        </div>

        <label className="field-label">
          Paste XML
          <textarea
            className="field-input monospace-block"
            onChange={(event) => setTextValue(event.target.value)}
            placeholder="<feedback>...</feedback>"
            rows={10}
            value={textValue}
          />
        </label>

        <label className="field-label">
          Upload file(s)
          <input
            className="field-input"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            type="file"
          />
        </label>

        {files.length ? (
          <div className="stack" style={{ gap: 8 }}>
            <span className="stat-label">Selected files</span>
            <div className="pill-row">
              {files.map((file) => (
                <span className="pill" key={`${file.name}-${file.size}`}>
                  {file.name}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {showMixedInputError ? <p className="error-text">Use either pasted XML or file uploads, not both.</p> : null}
        {showMissingInputError ? <p className="error-text">Paste XML or select one or more files.</p> : null}
        {mutationError ? <p className="error-text">{mutationError}</p> : null}
        {submittedJobId ? (
          <p className="status-text">
            Upload submitted as one ingest job.{" "}
            <Link className="inline-link" href={`/ingest-jobs/${submittedJobId}`}>
              Open job {submittedJobId}
            </Link>
          </p>
        ) : null}

        <button
          className="button-primary"
          disabled={uploadMutation.isPending || showMixedInputError || (!textValue.trim() && !files.length)}
          onClick={handleSubmit}
          type="button"
        >
          {uploadMutation.isPending ? "Submitting..." : "Submit upload"}
        </button>
      </section>
    </AppShell>
  );
}

function arrayBufferToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let index = 0; index < bytes.byteLength; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}

function utf8ToBase64(text: string): string {
  return arrayBufferToBase64(new TextEncoder().encode(text));
}

function isGzipFile(filename: string, bytes: Uint8Array): boolean {
  if (filename.endsWith(".gz") || filename.endsWith(".gzip")) {
    return true;
  }
  return bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
}
