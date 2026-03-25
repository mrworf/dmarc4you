"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { apiClient, ApiError } from "@/lib/api/client";
import type {
  DashboardSharesResponse,
  ShareDashboardBody,
  UsersResponse,
  UserRole,
} from "@/lib/api/types";

const accessOptions: Array<{ value: "viewer" | "manager"; label: string }> = [
  { value: "viewer", label: "Viewer" },
  { value: "manager", label: "Manager" },
];

export function DashboardSharingPanel({
  canManageShares,
  dashboardId,
  viewerOnly,
}: {
  canManageShares: boolean;
  dashboardId: string;
  viewerOnly: boolean;
}) {
  const queryClient = useQueryClient();
  const [selectedUserId, setSelectedUserId] = useState("");
  const [manualUserId, setManualUserId] = useState("");
  const [accessLevel, setAccessLevel] = useState<"viewer" | "manager">("viewer");
  const [pendingRemovalUserId, setPendingRemovalUserId] = useState<string | null>(null);

  const sharesQuery = useQuery({
    queryKey: ["dashboard-shares", dashboardId],
    queryFn: () => apiClient.get<DashboardSharesResponse>(`/api/v1/dashboards/${dashboardId}/shares`),
    enabled: !viewerOnly,
  });

  const usersQuery = useQuery({
    queryKey: ["shareable-users", dashboardId],
    queryFn: () => apiClient.get<UsersResponse>("/api/v1/users"),
    enabled: canManageShares,
    retry: false,
  });

  const shareMutation = useMutation({
    mutationFn: (payload: ShareDashboardBody) =>
      apiClient.post(`/api/v1/dashboards/${dashboardId}/share`, payload),
    onSuccess: async () => {
      setSelectedUserId("");
      setManualUserId("");
      await queryClient.invalidateQueries({ queryKey: ["dashboard-shares", dashboardId] });
    },
  });

  const unshareMutation = useMutation({
    mutationFn: (userId: string) => apiClient.delete(`/api/v1/dashboards/${dashboardId}/share/${userId}`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["dashboard-shares", dashboardId] });
    },
  });

  useEffect(() => {
    if (selectedUserId) {
      setManualUserId(selectedUserId);
    }
  }, [selectedUserId]);

  async function handleShare() {
    if (!manualUserId.trim()) {
      return;
    }
    await shareMutation.mutateAsync({
      user_id: manualUserId.trim(),
      access_level: accessLevel,
    });
  }

  if (viewerOnly) {
    return null;
  }

  const shareError = shareMutation.error instanceof ApiError ? shareMutation.error.message : null;
  const unshareError = unshareMutation.error instanceof ApiError ? unshareMutation.error.message : null;
  const usersUnavailable = usersQuery.error instanceof ApiError && usersQuery.error.status === 403;
  const users = usersQuery.data?.users ?? [];

  return (
    <div className="stack">
      <div>
        <h2 className="section-title">Dashboard access</h2>
        <p className="section-intro">Grant or remove access without leaving this page.</p>
      </div>

      {sharesQuery.isLoading ? <p className="status-text">Loading shares...</p> : null}
      {sharesQuery.error ? (
        <p className="error-text">
          {sharesQuery.error instanceof Error ? sharesQuery.error.message : "Failed to load shares"}
        </p>
      ) : null}

      {sharesQuery.data ? (
        sharesQuery.data.shares.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Access</th>
                  <th>Granted</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {sharesQuery.data.shares.map((share) => (
                  <tr key={share.user_id}>
                    <td>{share.username || share.user_id}</td>
                    <td>{share.access_level}</td>
                    <td>{new Date(share.granted_at).toLocaleString()}</td>
                    <td>
                      {canManageShares ? (
                        <button
                          className="button-link"
                          onClick={() => setPendingRemovalUserId(share.user_id)}
                          type="button"
                        >
                          Remove
                        </button>
                      ) : (
                        "n/a"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="status-text">Not shared with anyone yet.</p>
        )
      ) : null}

      {canManageShares ? (
        <div className="stack">
          <div>
            <p className="stat-label">Grant access</p>
            <p className="status-text" style={{ marginTop: 4 }}>Use the picker, or enter a user ID directly when needed.</p>
          </div>
          {usersQuery.isLoading ? <p className="status-text">Loading available users...</p> : null}
          {usersUnavailable ? (
            <p className="status-text">User picker unavailable for your role. Enter a `user_id` manually.</p>
          ) : null}
          {usersQuery.error && !usersUnavailable ? (
            <p className="error-text">
              {usersQuery.error instanceof Error ? usersQuery.error.message : "Failed to load users"}
            </p>
          ) : null}
          {users.length ? (
            <label className="field-label">
              Pick a user
              <select
                className="field-input"
                onChange={(event) => setSelectedUserId(event.target.value)}
                value={selectedUserId}
              >
                <option value="">Select user</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.username} ({formatRole(user.role)})
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="search-state-grid">
            <label className="field-label">
              User ID
              <input
                className="field-input"
                onChange={(event) => setManualUserId(event.target.value)}
                placeholder="usr_123"
                value={manualUserId}
              />
            </label>
            <label className="field-label">
              Access level
              <select
                className="field-input"
                onChange={(event) => setAccessLevel(event.target.value as "viewer" | "manager")}
                value={accessLevel}
              >
                {accessOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {shareError ? <p className="error-text">{shareError}</p> : null}
          {unshareError ? <p className="error-text">{unshareError}</p> : null}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button
              className="button-primary"
              disabled={shareMutation.isPending || !manualUserId.trim()}
              onClick={handleShare}
              type="button"
            >
              {shareMutation.isPending ? "Sharing..." : "Grant access"}
            </button>
            <button className="button-secondary" onClick={() => sharesQuery.refetch()} type="button">
              Refresh shares
            </button>
          </div>
        </div>
      ) : null}
      <ConfirmDialog
        confirmLabel="Remove access"
        description="Remove this user from the dashboard?"
        isPending={unshareMutation.isPending}
        onCancel={() => setPendingRemovalUserId(null)}
        onConfirm={() => {
          if (pendingRemovalUserId) {
            unshareMutation.mutate(pendingRemovalUserId, {
              onSuccess: async () => {
                setPendingRemovalUserId(null);
                await queryClient.invalidateQueries({ queryKey: ["dashboard-shares", dashboardId] });
              },
            });
          }
        }}
        open={Boolean(pendingRemovalUserId)}
        title="Remove access"
      />
    </div>
  );
}

function formatRole(role: UserRole): string {
  switch (role) {
    case "super-admin":
      return "super-admin";
    case "admin":
      return "admin";
    case "manager":
      return "manager";
    case "viewer":
      return "viewer";
    default:
      return role;
  }
}
