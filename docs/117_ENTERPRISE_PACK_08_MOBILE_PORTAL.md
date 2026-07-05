# Enterprise Pack 08 - Mobile and Unified Portal

## Purpose

Pack 08 builds a unified enterprise portal for mobile, tablet and desktop.

All portals share one login, one role permission model, one navigation contract and one component system.

## Portal Architecture

Supported portals:

- CEO
- Employee
- Store Manager
- Customer future
- Supplier future
- Admin

Single Sign-On:

- Existing `fp_session` session is the SSO foundation.
- One login grants access to all allowed modules.
- Navigation is filtered by role permissions.

## Shared Navigation

Navigation rules:

- Use the platform module registry as the source of truth.
- Hide modules that the role cannot access.
- Keep the same route contract across phone, tablet and desktop.
- Expose quick actions for portal, messages, tasks and Jarvis.

## Message Center

The message center aggregates:

- Notifications
- Approvals
- Tasks
- AI recommendations
- System alerts

## Task Center

The task center aggregates:

- Pending approvals
- Assigned tasks
- Workflow actions
- AI-generated suggestions

## Responsive Design

Design rules:

- Mobile-first
- Responsive layout
- Apple-style simplicity
- Consistent navigation
- Accessibility
- Light mode now, dark mode future

Shared components:

- Portal shell
- Topbar
- Role badge
- Quick actions
- App cards
- Message cards
- Task cards
- Responsive grid

## Implemented Contracts

- `/portal`
- `/api/portal`
- `/api/portal/framework`
- `/api/portal/sso`
- `/api/portal/navigation`
- `/api/portal/components`
- `/api/portal/messages`
- `/api/portal/tasks`
- `/api/portal/responsive`

## Acceptance

- Unified portal is available.
- Role-based navigation is available.
- Message center contract is available.
- Task center contract is available.
- Responsive component contract is available.
- Documentation and tests are updated.
