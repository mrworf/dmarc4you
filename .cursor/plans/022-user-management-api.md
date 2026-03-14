# Plan: User Management API (Slice 022)

## Goal

Implement user CRUD API so admins can create/manage users, enabling the full RBAC model.

## Scope (in)

- `GET /api/v1/users` — list users (super-admin: all; admin: users with ≥1 overlapping domain)
- `POST /api/v1/users` — create user (admin cannot create super-admin)
- `PUT /api/v1/users/{user_id}` — update username/role (admin cannot self-edit, cannot change admin/super-admin)
- `POST /api/v1/users/{user_id}/reset-password` — generate new random password
- `POST /api/v1/users/{user_id}/domains` — assign domain(s)
- `DELETE /api/v1/users/{user_id}/domains/{domain_id}` — remove domain assignment

## Scope (out)

- User deletion
- Self-service password/username change
- User management UI

## Files

### Created
- `backend/policies/user_policy.py`
- `backend/services/user_service.py`
- `backend/api/v1/handlers/users.py`
- `tests/integration/test_users.py`

### Edited
- `backend/api/v1/__init__.py`
- `docs/API_V1.md`

## Acceptance criteria

1. Super-admin can create any role including super-admin
2. Admin can create admin/manager/viewer but not super-admin (403)
3. Admin cannot change another admin's role or domains (403)
4. Admin cannot self-edit username (403)
5. List users returns domain-scoped results for admin
6. Reset password returns new password; old stops working
7. Audit events logged for create, update, reset-password, domain assign/remove
