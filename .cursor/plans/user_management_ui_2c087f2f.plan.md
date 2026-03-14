---
name: User Management UI
overview: Add a User Management UI page to the frontend SPA, enabling admins to create users, update usernames/roles, reset passwords, and manage domain assignments through the existing API endpoints.
todos:
  - id: users-html
    content: Add users-view HTML structure to index.html with list, forms, and nav link
    status: pending
  - id: users-js
    content: "Add users page logic to app.js: fetch, render, create, edit, reset-password, domain assign/remove"
    status: pending
  - id: users-css
    content: "Optional: add styling for users table and domain assignment UI"
    status: pending
  - id: manual-validation
    content: Test all user management flows for super-admin and admin roles
    status: pending
---

# User Management UI (Slice 023)

## Why This Slice

The User Management API (slice 022) is complete but has no UI. Admins must currently use API calls directly to create users or assign domains. This slice adds a frontend page following the same pattern as the existing API Keys UI.

## Scope (In)

- New "Users" link in navigation (visible to admin and super-admin only)
- Users view listing all visible users with role, domain assignments
- Create user form (username, role dropdown)
- Edit user inline or modal (username, role)
- Reset password button with confirmation
- Domain assignment: add/remove domains via checkboxes or multi-select
- Role-appropriate visibility (admins see scoped users, super-admin sees all)

## Scope (Out)

- User deletion (not implemented in API)
- Dashboard sharing assignment (separate slice)
- URL-based routing/state for users page

---

## Files to Edit

### [frontend/index.html](frontend/index.html)

Add new `users-view` div with:

- Users list table/list
- Create user form (username input, role select)
- Domain assignment fieldset
- Error/success message areas

Add "Users" link placeholder in nav (like API keys link).

### [frontend/js/app.js](frontend/js/app.js)

Add:

- `showUsers()` function to hide other views and show users view
- `loadUsersPage()` to fetch `GET /api/v1/users` and render list
- `fetchUsers()` helper
- Create user form handler → `POST /api/v1/users`
- Edit user handler → `PUT /api/v1/users/{id}`
- Reset password handler → `POST /api/v1/users/{id}/reset-password`
- Assign domains handler → `POST /api/v1/users/{id}/domains`
- Remove domain handler → `DELETE /api/v1/users/{id}/domains/{domain_id}`
- Users link click handler (conditional like audit/apikeys links)

### [frontend/css/main.css](frontend/css/main.css)

Optional: styling for user list table, role badges, domain assignment UI.

---

## UI Structure

```
Users
------
[← Back]

| Username | Role | Domains | Actions |
|----------|------|---------|---------|
| alice    | admin | dom_a, dom_b | [Edit] [Reset Password] |
| bob      | viewer | dom_a | [Edit] [Reset Password] [Manage Domains] |

--- Create User ---
Username: [___________]
Role: [viewer ▼]
[Create]

(Created! Password: xYz123...)
```

---

## Acceptance Criteria

1. "Users" link appears for admin and super-admin only
2. Users list shows username, role, domain count/names
3. Create user shows generated password once (with copy warning)
4. Edit user allows changing username and role (within RBAC bounds)
5. Reset password shows new password with warning
6. Domain assignment shows checkboxes of available domains
7. 403 errors show appropriate messages (e.g., "Cannot modify another admin")
8. Super-admin sees all users; admin sees only domain-overlapping users

---

## Tests and Validation

Manual validation (no new backend tests needed):

1. Log in as super-admin → Users link visible → list shows all users
2. Create user with role viewer → success, password shown
3. Edit user username → success
4. Reset password → new password works, old doesn't
5. Assign domain to user → user can now see that domain
6. Log in as admin → Users link visible → list shows only users with shared domains
7. As admin, try to create super-admin → error message
8. As admin, try to edit another admin → error message
9. Log in as viewer → Users link NOT visible