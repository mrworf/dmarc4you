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
import { useAuth } from "@/lib/auth/context";
import type {
  AssignUserDomainsBody,
  CreateUserBody,
  CreateUserResponse,
  DomainSummary,
  DomainsResponse,
  ListedUserSummary,
  ResetUserPasswordResponse,
  UpdateUserBody,
  UserDetailResponse,
  UserRole,
  UserSummary,
  UsersResponse,
} from "@/lib/api/types";

const createUserSchema = z.object({
  username: z.string().trim().min(1, "Username is required"),
  full_name: z.string().optional(),
  email: z.union([z.string().email("Enter a valid email"), z.literal("")]).optional(),
  role: z.enum(["super-admin", "admin", "manager", "viewer"]),
});

const editUserSchema = z.object({
  username: z.string().trim().min(1, "Username is required"),
  full_name: z.string().optional(),
  email: z.union([z.string().email("Enter a valid email"), z.literal("")]).optional(),
  role: z.enum(["super-admin", "admin", "manager", "viewer"]),
});

type CreateUserValues = z.infer<typeof createUserSchema>;
type EditUserValues = z.infer<typeof editUserSchema>;

type PasswordNotice = {
  password: string;
  username: string;
};

export function UsersContent() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [domainUserId, setDomainUserId] = useState<string | null>(null);
  const [selectedDomainIds, setSelectedDomainIds] = useState<string[]>([]);
  const [createdNotice, setCreatedNotice] = useState<PasswordNotice | null>(null);
  const [resetNotice, setResetNotice] = useState<PasswordNotice | null>(null);
  const [resetTarget, setResetTarget] = useState<ListedUserSummary | null>(null);

  const createForm = useForm<CreateUserValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: {
      username: "",
      full_name: "",
      email: "",
      role: "viewer",
    },
  });

  const editForm = useForm<EditUserValues>({
    resolver: zodResolver(editUserSchema),
    defaultValues: {
      username: "",
      full_name: "",
      email: "",
      role: "viewer",
    },
  });

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiClient.get<UsersResponse>("/api/v1/users"),
    retry: false,
  });

  const domainsQuery = useQuery({
    queryKey: ["domains"],
    queryFn: () => apiClient.get<DomainsResponse>("/api/v1/domains"),
    retry: false,
  });

  const editUserQuery = useQuery({
    queryKey: ["user", editingUserId],
    queryFn: () => apiClient.get<UserDetailResponse>(`/api/v1/users/${editingUserId}`),
    enabled: Boolean(editingUserId),
    retry: false,
  });

  const domainUserQuery = useQuery({
    queryKey: ["user-domains", domainUserId],
    queryFn: () => apiClient.get<UserDetailResponse>(`/api/v1/users/${domainUserId}`),
    enabled: Boolean(domainUserId),
    retry: false,
  });

  useEffect(() => {
    if (!editUserQuery.data?.user) {
      return;
    }
    editForm.reset({
      username: editUserQuery.data.user.username,
      full_name: editUserQuery.data.user.full_name ?? "",
      email: editUserQuery.data.user.email ?? "",
      role: editUserQuery.data.user.role,
    });
  }, [editForm, editUserQuery.data]);

  useEffect(() => {
    setSelectedDomainIds(domainUserQuery.data?.user.domain_ids ?? []);
  }, [domainUserQuery.data]);

  const createUserMutation = useMutation({
    mutationFn: (body: CreateUserBody) => apiClient.post<CreateUserResponse>("/api/v1/users", body),
    onSuccess: async (data) => {
      createForm.reset({
        username: "",
        full_name: "",
        email: "",
        role: "viewer",
      });
      setCreatedNotice({ username: data.user.username, password: data.password });
      setResetNotice(null);
      setIsCreateOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, body }: { userId: string; body: UpdateUserBody }) =>
      apiClient.put<UserDetailResponse>(`/api/v1/users/${userId}`, body),
    onSuccess: async (_, variables) => {
      setEditingUserId(null);
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      await queryClient.invalidateQueries({ queryKey: ["user", variables.userId] });
    },
  });

  const resetPasswordMutation = useMutation({
    mutationFn: async (targetUser: ListedUserSummary) => {
      const result = await apiClient.post<ResetUserPasswordResponse>(`/api/v1/users/${targetUser.id}/reset-password`);
      return { ...result, username: targetUser.username };
    },
  });

  const assignDomainsMutation = useMutation({
    mutationFn: async ({
      currentIds,
      selectedIds,
      userId,
    }: {
      currentIds: string[];
      selectedIds: string[];
      userId: string;
    }) => {
      const toAdd = selectedIds.filter((domainId) => !currentIds.includes(domainId));
      const toRemove = currentIds.filter((domainId) => !selectedIds.includes(domainId));

      if (toAdd.length) {
        const body: AssignUserDomainsBody = { domain_ids: toAdd };
        await apiClient.post(`/api/v1/users/${userId}/domains`, body);
      }

      for (const domainId of toRemove) {
        await apiClient.delete(`/api/v1/users/${userId}/domains/${domainId}`);
      }

      return apiClient.get<UserDetailResponse>(`/api/v1/users/${userId}`);
    },
    onSuccess: async (data, variables) => {
      setSelectedDomainIds(data.user.domain_ids ?? []);
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      await queryClient.invalidateQueries({ queryKey: ["user-domains", variables.userId] });
    },
  });

  async function handleCreateUser(values: CreateUserValues) {
    const body: CreateUserBody = {
      username: values.username.trim(),
      role: values.role,
      full_name: values.full_name?.trim() ? values.full_name.trim() : null,
      email: values.email?.trim() ? values.email.trim() : null,
    };
    await createUserMutation.mutateAsync(body);
  }

  async function handleEditUser(values: EditUserValues) {
    if (!editingUserId) {
      return;
    }
    const body: UpdateUserBody = {
      username: values.username.trim(),
      role: values.role,
      full_name: values.full_name?.trim() ? values.full_name.trim() : null,
      email: values.email?.trim() ? values.email.trim() : null,
    };
    await updateUserMutation.mutateAsync({ userId: editingUserId, body });
  }

  async function handleSaveDomains() {
    if (!domainUserId || !domainUserQuery.data?.user) {
      return;
    }
    await assignDomainsMutation.mutateAsync({
      userId: domainUserId,
      currentIds: domainUserQuery.data.user.domain_ids ?? [],
      selectedIds: selectedDomainIds,
    });
  }

  const users = usersQuery.data?.users ?? [];
  const visibleDomains = domainsQuery.data?.domains ?? [];
  const roleOptions = getAssignableRoleOptions(currentUser?.role);
  const createError = createUserMutation.error instanceof ApiError ? createUserMutation.error.message : null;
  const updateError = updateUserMutation.error instanceof ApiError ? updateUserMutation.error.message : null;
  const resetError = resetPasswordMutation.error instanceof ApiError ? resetPasswordMutation.error.message : null;
  const domainError = assignDomainsMutation.error instanceof ApiError ? assignDomainsMutation.error.message : null;
  const userCountByRole = {
    admins: users.filter((entry) => entry.role === "admin" || entry.role === "super-admin").length,
    managers: users.filter((entry) => entry.role === "manager").length,
    viewers: users.filter((entry) => entry.role === "viewer").length,
  };

  return (
    <AppShell
      title="Users"
      description="Manage local accounts, roles, and domain access for your team."
      actions={
        <div className="section-actions">
          <button className="button-primary" onClick={() => setIsCreateOpen(true)} type="button">
            Create user
          </button>
          <button
            className="button-secondary"
            onClick={() => {
              usersQuery.refetch();
              domainsQuery.refetch();
              if (editingUserId) {
                editUserQuery.refetch();
              }
              if (domainUserId) {
                domainUserQuery.refetch();
              }
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
          <p className="stat-label">Visible users</p>
          <p className="stat-value">{users.length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Admins</p>
          <p className="stat-value">{userCountByRole.admins}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Managers</p>
          <p className="stat-value">{userCountByRole.managers}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Viewers</p>
          <p className="stat-value">{userCountByRole.viewers}</p>
        </article>
      </section>

      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">User directory</h2>
            <p className="section-intro">Open a row action to edit account details, reset a password, or adjust domain access.</p>
          </div>
        </div>

        {usersQuery.isLoading ? <p className="status-text">Loading users...</p> : null}
        {usersQuery.error ? (
          <p className="error-text">{usersQuery.error instanceof Error ? usersQuery.error.message : "Failed to load users"}</p>
        ) : null}

        {!usersQuery.isLoading && !usersQuery.error && !users.length ? (
          <p className="status-text">No users are visible for this account yet.</p>
        ) : null}

        {users.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Full name</th>
                  <th>Email</th>
                  <th>Domains</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((entry) => {
                  const canEdit = canEditUser(currentUser, entry);
                  const canAssignDomains = canManageDomains(currentUser, entry);

                  return (
                    <tr key={entry.id}>
                      <td className="monospace">{entry.username}</td>
                      <td>{entry.role}</td>
                      <td>{entry.full_name || "n/a"}</td>
                      <td>{entry.email || "n/a"}</td>
                      <td>{formatDomainList(entry.domain_ids, visibleDomains)}</td>
                      <td>
                        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                          {canEdit ? (
                            <>
                              <button
                                className="button-link"
                                onClick={() => {
                                  setEditingUserId(entry.id);
                                  setDomainUserId(null);
                                  setCreatedNotice(null);
                                }}
                                type="button"
                              >
                                Edit
                              </button>
                              <button className="button-link" onClick={() => setResetTarget(entry)} type="button">
                                Reset password
                              </button>
                            </>
                          ) : null}
                          {canAssignDomains ? (
                            <button
                              className="button-link"
                              onClick={() => {
                                setDomainUserId(entry.id);
                                setEditingUserId(null);
                              }}
                              type="button"
                            >
                              Domains
                            </button>
                          ) : null}
                          {!canEdit && !canAssignDomains ? <span className="status-text">Not available</span> : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <SlideOverPanel
        description="Create a local account and choose the highest role your session is allowed to grant."
        onClose={() => setIsCreateOpen(false)}
        open={isCreateOpen}
        title="Create user"
      >
        <form className="stack" onSubmit={createForm.handleSubmit(handleCreateUser)}>
          <div className="search-state-grid">
            <label className="field-label">
              Username
              <input className="field-input" {...createForm.register("username")} placeholder="alice" />
              {createForm.formState.errors.username ? (
                <span className="error-text">{createForm.formState.errors.username.message}</span>
              ) : null}
            </label>
            <label className="field-label">
              Role
              <select className="field-input" {...createForm.register("role")}>
                {roleOptions.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Full name
              <input className="field-input" {...createForm.register("full_name")} placeholder="Optional" />
            </label>
            <label className="field-label">
              Email
              <input className="field-input" {...createForm.register("email")} placeholder="Optional" type="email" />
              {createForm.formState.errors.email ? (
                <span className="error-text">{createForm.formState.errors.email.message}</span>
              ) : null}
            </label>
          </div>
          {createError ? <p className="error-text">{createError}</p> : null}
          <button className="button-primary" disabled={createUserMutation.isPending} type="submit">
            {createUserMutation.isPending ? "Creating..." : "Create user"}
          </button>
        </form>
      </SlideOverPanel>

      <SlideOverPanel
        description="Update the account details for this user."
        onClose={() => setEditingUserId(null)}
        open={Boolean(editingUserId)}
        title="Edit user"
      >
        {editUserQuery.isLoading ? <p className="status-text">Loading user details...</p> : null}
        {editUserQuery.error ? (
          <p className="error-text">
            {editUserQuery.error instanceof Error ? editUserQuery.error.message : "Failed to load user details"}
          </p>
        ) : null}
        {editUserQuery.data ? (
          <form className="stack" onSubmit={editForm.handleSubmit(handleEditUser)}>
            <div className="search-state-grid">
              <label className="field-label">
                Username
                <input className="field-input" {...editForm.register("username")} />
                {editForm.formState.errors.username ? (
                  <span className="error-text">{editForm.formState.errors.username.message}</span>
                ) : null}
              </label>
              <label className="field-label">
                Role
                <select className="field-input" {...editForm.register("role")}>
                  {roleOptions.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field-label">
                Full name
                <input className="field-input" {...editForm.register("full_name")} placeholder="Optional" />
              </label>
              <label className="field-label">
                Email
                <input className="field-input" {...editForm.register("email")} placeholder="Optional" type="email" />
                {editForm.formState.errors.email ? (
                  <span className="error-text">{editForm.formState.errors.email.message}</span>
                ) : null}
              </label>
            </div>
            {updateError ? <p className="error-text">{updateError}</p> : null}
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button className="button-primary" disabled={updateUserMutation.isPending} type="submit">
                {updateUserMutation.isPending ? "Saving..." : "Save user"}
              </button>
              <button className="button-secondary" onClick={() => setEditingUserId(null)} type="button">
                Cancel
              </button>
            </div>
          </form>
        ) : null}
      </SlideOverPanel>

      <SlideOverPanel
        description={`Choose the active domains ${domainUserQuery.data?.user.username ?? "this user"} should be able to access.`}
        error={domainError ? <p className="error-text">{domainError}</p> : null}
        onClose={() => setDomainUserId(null)}
        open={Boolean(domainUserId)}
        title="Manage domains"
      >
        {domainUserQuery.isLoading ? <p className="status-text">Loading current assignments...</p> : null}
        {domainUserQuery.error ? (
          <p className="error-text">
            {domainUserQuery.error instanceof Error ? domainUserQuery.error.message : "Failed to load domain assignments"}
          </p>
        ) : null}
        {domainsQuery.isLoading ? <p className="status-text">Loading visible domains...</p> : null}
        {visibleDomains.length ? (
          <div className="checkbox-grid">
            {visibleDomains.map((domain) => (
              <label className="checkbox-card" key={domain.id}>
                <input
                  checked={selectedDomainIds.includes(domain.id)}
                  onChange={() => setSelectedDomainIds(toggleSelection(selectedDomainIds, domain.id))}
                  type="checkbox"
                />
                <span>{domain.name}</span>
              </label>
            ))}
          </div>
        ) : (
          <p className="status-text">No visible active domains are available for assignment.</p>
        )}
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSaveDomains();
          }}
        >
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button className="button-primary" disabled={assignDomainsMutation.isPending || domainUserQuery.isLoading} type="submit">
              {assignDomainsMutation.isPending ? "Saving..." : "Save domains"}
            </button>
            <button className="button-secondary" onClick={() => setDomainUserId(null)} type="button">
              Close
            </button>
          </div>
        </form>
      </SlideOverPanel>

      <CredentialDialog
        description={`Copy the password for ${createdNotice?.username ?? "this user"} now. It will not be shown again.`}
        label="Temporary password"
        onClose={() => setCreatedNotice(null)}
        open={Boolean(createdNotice)}
        title="User created"
        value={createdNotice?.password ?? ""}
      />

      <CredentialDialog
        description={`Copy the new password for ${resetNotice?.username ?? "this user"} now. It will not be shown again.`}
        label="Temporary password"
        onClose={() => setResetNotice(null)}
        open={Boolean(resetNotice)}
        title="Password reset"
        value={resetNotice?.password ?? ""}
      />

      <ConfirmDialog
        confirmLabel="Reset password"
        description={resetTarget ? `Reset the password for ${resetTarget.username}?` : ""}
        error={resetError ? <p className="error-text">{resetError}</p> : null}
        isPending={resetPasswordMutation.isPending}
        onCancel={() => setResetTarget(null)}
        onConfirm={() => {
          if (resetTarget) {
            resetPasswordMutation.mutate(resetTarget, {
              onSuccess: (data) => {
                setResetNotice({ username: data.username, password: data.password });
                setCreatedNotice(null);
                setResetTarget(null);
              },
            });
          }
        }}
        open={Boolean(resetTarget)}
        title="Reset password"
      />
    </AppShell>
  );
}

function getAssignableRoleOptions(currentRole: UserRole | undefined): UserRole[] {
  if (currentRole === "super-admin") {
    return ["viewer", "manager", "admin", "super-admin"];
  }
  return ["viewer", "manager", "admin"];
}

function canEditUser(currentUser: UserSummary | null, targetUser: ListedUserSummary): boolean {
  if (!currentUser) {
    return false;
  }
  if (currentUser.id === targetUser.id) {
    return false;
  }
  if (currentUser.role === "admin" && (targetUser.role === "admin" || targetUser.role === "super-admin")) {
    return false;
  }
  return true;
}

function canManageDomains(currentUser: UserSummary | null, targetUser: ListedUserSummary): boolean {
  if (!currentUser) {
    return false;
  }
  if (currentUser.role === "admin" && (targetUser.role === "admin" || targetUser.role === "super-admin")) {
    return false;
  }
  return true;
}

function formatDomainList(domainIds: string[] | undefined, visibleDomains: DomainSummary[]): string {
  if (!domainIds?.length) {
    return "0";
  }
  const names = domainIds.map((domainId) => visibleDomains.find((domain) => domain.id === domainId)?.name ?? domainId);
  return names.join(", ");
}

function toggleSelection(selectedDomainIds: string[], domainId: string): string[] {
  if (selectedDomainIds.includes(domainId)) {
    return selectedDomainIds.filter((entry) => entry !== domainId);
  }
  return [...selectedDomainIds, domainId];
}
