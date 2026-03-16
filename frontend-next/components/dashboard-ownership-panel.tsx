"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, ApiError } from "@/lib/api/client";
import type {
  DashboardDetailResponse,
  ListedUserSummary,
  TransferDashboardOwnershipBody,
  UsersResponse,
} from "@/lib/api/types";

export function DashboardOwnershipPanel({
  canTransferOwnership,
  dashboard,
}: {
  canTransferOwnership: boolean;
  dashboard: DashboardDetailResponse;
}) {
  const queryClient = useQueryClient();
  const [selectedUserId, setSelectedUserId] = useState("");

  const usersQuery = useQuery({
    queryKey: ["ownership-users", dashboard.id],
    queryFn: () => apiClient.get<UsersResponse>("/api/v1/users"),
    enabled: canTransferOwnership,
  });

  const eligibleUsers = useMemo(
    () =>
      (usersQuery.data?.users ?? []).filter((user) => user.id !== dashboard.owner_user_id),
    [dashboard.owner_user_id, usersQuery.data?.users],
  );

  const transferOwnership = useMutation({
    mutationFn: (body: TransferDashboardOwnershipBody) =>
      apiClient.post<DashboardDetailResponse>(`/api/v1/dashboards/${dashboard.id}/owner`, body),
    onSuccess: async (updatedDashboard) => {
      queryClient.setQueryData(["dashboard", dashboard.id], updatedDashboard);
      await queryClient.invalidateQueries({ queryKey: ["dashboards"] });
      setSelectedUserId("");
    },
  });

  if (!canTransferOwnership) {
    return null;
  }

  const mutationError =
    transferOwnership.error instanceof ApiError ? transferOwnership.error.message : null;

  return (
    <div className="stack">
      <div>
        <h2 className="section-title">Transfer ownership</h2>
        <p className="section-intro">Choose another eligible teammate to own this dashboard.</p>
      </div>
      {usersQuery.isLoading ? <p className="status-text">Loading eligible users...</p> : null}
      {usersQuery.error ? (
        <p className="error-text">
          {usersQuery.error instanceof Error ? usersQuery.error.message : "Failed to load users"}
        </p>
      ) : null}
      {eligibleUsers.length ? (
        <label className="field-label">
          New owner
          <select
            className="field-input"
            onChange={(event) => setSelectedUserId(event.target.value)}
            value={selectedUserId}
          >
            <option value="">Select user</option>
            {eligibleUsers.map((user) => (
              <option key={user.id} value={user.id}>
                {formatOwnershipOption(user)}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className="status-text">No alternate visible users are currently available for transfer.</p>
      )}
      {mutationError ? <p className="error-text">{mutationError}</p> : null}
      <button
        className="button-primary"
        disabled={transferOwnership.isPending || !selectedUserId}
        onClick={() => transferOwnership.mutate({ user_id: selectedUserId })}
        type="button"
      >
        {transferOwnership.isPending ? "Transferring..." : "Transfer ownership"}
      </button>
    </div>
  );
}

function formatOwnershipOption(user: ListedUserSummary): string {
  return `${user.username} (${user.role})`;
}
