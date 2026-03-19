"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { CredentialDialog } from "@/components/credential-dialog";
import { SlideOverPanel } from "@/components/slide-over-panel";
import { apiClient, ApiError } from "@/lib/api/client";
import type {
  ApiKeySummary,
  ApiKeysResponse,
  CreateApiKeyBody,
  CreateApiKeyResponse,
  DomainSummary,
  DomainsResponse,
  UpdateApiKeyBody,
  UpdateApiKeyResponse,
} from "@/lib/api/types";

const availableScopes = ["reports:ingest", "domains:monitor"] as const;

const createApiKeySchema = z.object({
  nickname: z.string().trim().min(1, "Nickname is required"),
  description: z.string().optional(),
  domain_ids: z.array(z.string()).min(1, "Select at least one domain"),
  scopes: z.array(z.string()).min(1, "Select at least one scope"),
});

const editApiKeySchema = z.object({
  nickname: z.string().trim().min(1, "Nickname is required"),
  description: z.string().optional(),
  scopes: z.array(z.string()).min(1, "Select at least one scope"),
});

type CreateApiKeyValues = z.infer<typeof createApiKeySchema>;
type EditApiKeyValues = z.infer<typeof editApiKeySchema>;

type SecretNotice = {
  nickname: string;
  secret: string;
};

export function ApiKeysContent() {
  const queryClient = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingKeyId, setEditingKeyId] = useState<string | null>(null);
  const [secretNotice, setSecretNotice] = useState<SecretNotice | null>(null);
  const [deleteKeyId, setDeleteKeyId] = useState<string | null>(null);

  const createForm = useForm<CreateApiKeyValues>({
    resolver: zodResolver(createApiKeySchema),
    defaultValues: {
      nickname: "",
      description: "",
      domain_ids: [],
      scopes: ["reports:ingest"],
    },
  });

  const editForm = useForm<EditApiKeyValues>({
    resolver: zodResolver(editApiKeySchema),
    defaultValues: {
      nickname: "",
      description: "",
      scopes: ["reports:ingest"],
    },
  });

  const apiKeysQuery = useQuery({
    queryKey: ["apikeys"],
    queryFn: () => apiClient.get<ApiKeysResponse>("/api/v1/apikeys"),
    retry: false,
  });

  const domainsQuery = useQuery({
    queryKey: ["domains"],
    queryFn: () => apiClient.get<DomainsResponse>("/api/v1/domains"),
    retry: false,
  });

  const apiKeys = apiKeysQuery.data?.keys ?? [];
  const visibleDomains = domainsQuery.data?.domains ?? [];
  const editingKey = apiKeys.find((key) => key.id === editingKeyId) ?? null;

  useEffect(() => {
    if (!editingKey) {
      return;
    }
    editForm.reset({
      nickname: editingKey.nickname,
      description: editingKey.description ?? "",
      scopes: editingKey.scopes,
    });
  }, [editForm, editingKey]);

  const createApiKeyMutation = useMutation({
    mutationFn: (body: CreateApiKeyBody) => apiClient.post<CreateApiKeyResponse>("/api/v1/apikeys", body),
    onSuccess: async (data) => {
      createForm.reset({
        nickname: "",
        description: "",
        domain_ids: [],
        scopes: ["reports:ingest"],
      });
      setSecretNotice({ nickname: data.nickname, secret: data.key });
      setIsCreateOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["apikeys"] });
    },
  });

  const updateApiKeyMutation = useMutation({
    mutationFn: ({ body, keyId }: { keyId: string; body: UpdateApiKeyBody }) =>
      apiClient.put<UpdateApiKeyResponse>(`/api/v1/apikeys/${keyId}`, body),
    onSuccess: async (_, variables) => {
      setEditingKeyId(null);
      await queryClient.invalidateQueries({ queryKey: ["apikeys"] });
      await queryClient.invalidateQueries({ queryKey: ["apikey", variables.keyId] });
    },
  });

  const deleteApiKeyMutation = useMutation({
    mutationFn: (keyId: string) => apiClient.delete(`/api/v1/apikeys/${keyId}`),
    onSuccess: async () => {
      if (editingKeyId) {
        setEditingKeyId(null);
      }
      await queryClient.invalidateQueries({ queryKey: ["apikeys"] });
    },
  });

  async function handleCreateApiKey(values: CreateApiKeyValues) {
    const body: CreateApiKeyBody = {
      nickname: values.nickname.trim(),
      description: values.description?.trim() ?? "",
      domain_ids: values.domain_ids,
      scopes: values.scopes,
    };
    await createApiKeyMutation.mutateAsync(body);
  }

  async function handleEditApiKey(values: EditApiKeyValues) {
    if (!editingKeyId) {
      return;
    }
    const body: UpdateApiKeyBody = {
      nickname: values.nickname.trim(),
      description: values.description?.trim() ?? "",
      scopes: values.scopes,
    };
    await updateApiKeyMutation.mutateAsync({ keyId: editingKeyId, body });
  }

  async function handleDeleteApiKey(key: ApiKeySummary) {
    setDeleteKeyId(key.id);
  }

  const createError = createApiKeyMutation.error instanceof ApiError ? createApiKeyMutation.error.message : null;
  const updateError = updateApiKeyMutation.error instanceof ApiError ? updateApiKeyMutation.error.message : null;
  const deleteError = deleteApiKeyMutation.error instanceof ApiError ? deleteApiKeyMutation.error.message : null;
  const keyCountByScope = {
    ingest: apiKeys.filter((key) => key.scopes.includes("reports:ingest")).length,
    monitor: apiKeys.filter((key) => key.scopes.includes("domains:monitor")).length,
  };

  return (
    <AppShell
      title="API Keys"
      description="Manage ingest credentials for your visible domains."
      actions={
        <div className="section-actions">
          <button className="button-primary" onClick={() => setIsCreateOpen(true)} type="button">
            Create API key
          </button>
          <button
            className="button-secondary"
            onClick={() => {
              apiKeysQuery.refetch();
              domainsQuery.refetch();
            }}
            type="button"
          >
            Refresh
          </button>
        </div>
      }
    >
      <section className="panel-grid">
        <article className="stat-card">
          <p className="stat-label">Visible keys</p>
          <p className="stat-value">{apiKeys.length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Ingest scope</p>
          <p className="stat-value">{keyCountByScope.ingest}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Monitor scope</p>
          <p className="stat-value">{keyCountByScope.monitor}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Visible domains</p>
          <p className="stat-value">{visibleDomains.length}</p>
        </article>
      </section>

      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">Key inventory</h2>
            <p className="section-intro">Review current credentials, then edit or revoke them from the row actions.</p>
          </div>
        </div>

        {apiKeysQuery.isLoading ? <p className="status-text">Loading API keys...</p> : null}
        {apiKeysQuery.error ? (
          <p className="error-text">
            {apiKeysQuery.error instanceof Error ? apiKeysQuery.error.message : "Failed to load API keys"}
          </p>
        ) : null}

        {!apiKeysQuery.isLoading && !apiKeysQuery.error && !apiKeys.length ? (
          <p className="status-text">No API keys are visible for this account yet.</p>
        ) : null}

        {apiKeys.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nickname</th>
                  <th>Description</th>
                  <th>Domains</th>
                  <th>Scopes</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {apiKeys.map((key) => (
                  <tr key={key.id}>
                    <td className="monospace">{key.nickname}</td>
                    <td>{key.description || "n/a"}</td>
                    <td>{formatKeyDomains(key, visibleDomains)}</td>
                    <td>{key.scopes.join(", ") || "n/a"}</td>
                    <td>{new Date(key.created_at).toLocaleString()}</td>
                    <td>
                      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                        <button
                          className="button-link"
                          onClick={() => {
                            setEditingKeyId(key.id);
                            setSecretNotice(null);
                          }}
                          type="button"
                        >
                          Edit
                        </button>
                        <button className="button-link" onClick={() => handleDeleteApiKey(key)} type="button">
                          Revoke
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <SlideOverPanel
        description="Choose a nickname, set the domain scope, and create a new ingest credential."
        onClose={() => setIsCreateOpen(false)}
        open={isCreateOpen}
        title="Create API key"
      >
        <form className="stack" onSubmit={createForm.handleSubmit(handleCreateApiKey)}>
          <div className="search-state-grid">
            <label className="field-label">
              Nickname
              <input className="field-input" {...createForm.register("nickname")} placeholder="mx-gateway" />
              {createForm.formState.errors.nickname ? (
                <span className="error-text">{createForm.formState.errors.nickname.message}</span>
              ) : null}
            </label>
            <label className="field-label">
              Description
              <input className="field-input" {...createForm.register("description")} placeholder="Optional" />
            </label>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <span className="field-label" style={{ gap: 0 }}>
              Domains
            </span>
            {visibleDomains.length ? (
              visibleDomains.map((domain) => (
                <label
                  key={domain.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "12px 14px",
                    border: "1px solid var(--line)",
                    borderRadius: 14,
                    background: "rgba(255,255,255,0.75)",
                  }}
                >
                  <input type="checkbox" value={domain.id} {...createForm.register("domain_ids")} />
                  <span>{domain.name}</span>
                </label>
              ))
            ) : (
              <p className="status-text">No visible active domains are available yet.</p>
            )}
            {createForm.formState.errors.domain_ids ? (
              <span className="error-text">{createForm.formState.errors.domain_ids.message}</span>
            ) : null}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <span className="field-label" style={{ gap: 0 }}>
              Scopes
            </span>
            {availableScopes.map((scope) => (
              <label className="checkbox-card" key={scope}>
                <input type="checkbox" value={scope} {...createForm.register("scopes")} />
                <span>{scope}</span>
              </label>
            ))}
            {createForm.formState.errors.scopes ? (
              <span className="error-text">{createForm.formState.errors.scopes.message}</span>
            ) : null}
          </div>
          {createError ? <p className="error-text">{createError}</p> : null}
          <button className="button-primary" disabled={createApiKeyMutation.isPending || !visibleDomains.length} type="submit">
            {createApiKeyMutation.isPending ? "Creating..." : "Create API key"}
          </button>
        </form>
      </SlideOverPanel>

      {editingKey ? (
        <SlideOverPanel
          description="Update the label and scopes for this key. Domain bindings stay unchanged."
          onClose={() => setEditingKeyId(null)}
          open={Boolean(editingKey)}
          title="Edit API key"
        >
          <div className="domain-meta">
            <span className="monospace">ID {editingKey.id}</span>
            <span>Domains {formatKeyDomains(editingKey, visibleDomains)}</span>
          </div>
          <form className="stack" onSubmit={editForm.handleSubmit(handleEditApiKey)}>
            <div className="search-state-grid">
              <label className="field-label">
                Nickname
                <input className="field-input" {...editForm.register("nickname")} />
                {editForm.formState.errors.nickname ? (
                  <span className="error-text">{editForm.formState.errors.nickname.message}</span>
                ) : null}
              </label>
              <label className="field-label">
                Description
                <input className="field-input" {...editForm.register("description")} placeholder="Optional" />
              </label>
            </div>
            <div className="stack" style={{ gap: 10 }}>
              <span className="field-label" style={{ gap: 0 }}>
                Scopes
              </span>
              {availableScopes.map((scope) => (
                <label className="checkbox-card" key={scope}>
                  <input type="checkbox" value={scope} {...editForm.register("scopes")} />
                  <span>{scope}</span>
                </label>
              ))}
              {editForm.formState.errors.scopes ? (
                <span className="error-text">{editForm.formState.errors.scopes.message}</span>
              ) : null}
            </div>
            {updateError ? <p className="error-text">{updateError}</p> : null}
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button className="button-primary" disabled={updateApiKeyMutation.isPending} type="submit">
                {updateApiKeyMutation.isPending ? "Saving..." : "Save API key"}
              </button>
              <button className="button-secondary" onClick={() => setEditingKeyId(null)} type="button">
                Cancel
              </button>
            </div>
          </form>
        </SlideOverPanel>
      ) : null}

      <CredentialDialog
        description={`Copy the secret for ${secretNotice?.nickname ?? "this key"} now. It will not be shown again.`}
        label="Raw secret"
        onClose={() => setSecretNotice(null)}
        open={Boolean(secretNotice)}
        title="API key created"
        value={secretNotice?.secret ?? ""}
      />

      <ConfirmDialog
        confirmLabel="Revoke key"
        confirmTone="danger"
        description={
          deleteKeyId
            ? `Revoke this API key now? Any clients using it will stop working immediately.`
            : ""
        }
        error={deleteError ? <p className="error-text">{deleteError}</p> : null}
        isPending={deleteApiKeyMutation.isPending}
        onCancel={() => setDeleteKeyId(null)}
        onConfirm={() => {
          if (deleteKeyId) {
            deleteApiKeyMutation.mutate(deleteKeyId, {
              onSuccess: async () => {
                setDeleteKeyId(null);
                if (editingKeyId === deleteKeyId) {
                  setEditingKeyId(null);
                }
                await queryClient.invalidateQueries({ queryKey: ["apikeys"] });
              },
            });
          }
        }}
        open={Boolean(deleteKeyId)}
        title="Revoke API key"
      />
    </AppShell>
  );
}

function formatKeyDomains(key: ApiKeySummary, visibleDomains: DomainSummary[]): string {
  if (key.domain_names.length) {
    return key.domain_names.join(", ");
  }
  if (!key.domain_ids.length) {
    return "n/a";
  }
  return key.domain_ids
    .map((domainId) => visibleDomains.find((domain) => domain.id === domainId)?.name ?? domainId)
    .join(", ");
}
