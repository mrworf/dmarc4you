# Plan: User Management UI (Slice 023)

## Goal

Add a User Management UI page to the frontend SPA, enabling admins to create users, update usernames/roles, reset passwords, and manage domain assignments through the existing API endpoints (slice 022).

## Scope (in)

- New "Users" link in navigation (visible to admin and super-admin only)
- Users view listing all visible users with role, domain count
- Create user form (username, role dropdown)
- Edit user form (username, role)
- Reset password button with confirmation and alert showing new password
- Domain assignment via checkboxes

## Scope (out)

- User deletion (not implemented in API)
- Dashboard sharing assignment (separate slice)
- URL-based routing/state for users page

## Files edited

- `frontend/index.html` — users-view HTML, nav link
- `frontend/js/app.js` — users page logic
- `frontend/css/main.css` — styling

## Acceptance criteria

1. "Users" link appears for admin and super-admin only ✓
2. Users list shows username, role, domain count ✓
3. Create user shows generated password ✓
4. Edit user allows changing username and role ✓
5. Reset password shows new password with warning ✓
6. Domain assignment shows checkboxes ✓
7. 403 errors show appropriate messages ✓
