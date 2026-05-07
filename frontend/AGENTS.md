# Frontend Agent Notes

## Purpose

The `frontend/` directory contains a standalone Next.js Kanban demo that currently runs without backend integration.

## Stack

- Next.js (App Router) + React + TypeScript
- Tailwind CSS v4 styling via `src/app/globals.css`
- Drag and drop via `@dnd-kit` (`core`, `sortable`, `utilities`)
- Testing:
  - Vitest + Testing Library for component and logic tests
  - Playwright for e2e browser tests

## Current App Structure

- `src/app/page.tsx`: renders `KanbanBoard`.
- `src/components/KanbanBoard.tsx`: main board state and interaction handlers.
- `src/components/KanbanColumn.tsx`: per-column UI, title rename input, sortable area, add-card form.
- `src/components/KanbanCard.tsx`: draggable card UI and delete button.
- `src/components/NewCardForm.tsx`: inline create-card form (title required).
- `src/lib/kanban.ts`: core types, initial board data, card move logic, ID creation helper.

## Behavior Implemented Today

- Single in-memory board with 5 columns and seeded cards.
- Column titles can be renamed inline.
- Cards can be dragged within a column and across columns.
- New cards can be added to a column.
- Cards can be removed from a column.
- Frontend now uses backend APIs for persistence when available.
- Includes a sidebar AI assistant chat widget that calls backend AI endpoints.

## Important Limits of Current Frontend

- Card content is not editable after creation from the standard card UI.
- Chat history in sidebar is in-memory per page load.
- Full auth + persistence + AI integration depends on backend availability.

## Visual System

- Color variables in `src/app/globals.css` match project palette:
  - accent yellow (`--accent-yellow`)
  - primary blue (`--primary-blue`)
  - secondary purple (`--secondary-purple`)
  - dark navy (`--navy-dark`)
  - gray text (`--gray-text`)

## Available Commands

- `npm run dev`
- `npm run build`
- `npm run start`
- `npm run lint`
- `npm run test:unit`
- `npm run test:e2e`
- `npm run test:all`

## Existing Test Coverage

- `src/components/KanbanBoard.test.tsx`
  - renders five columns
  - renames a column
  - adds and removes a card
- `src/lib/kanban.test.ts`
  - same-column reorder
  - cross-column move
  - drop-to-column-end behavior
- `tests/kanban.spec.ts`
  - board loads
  - add card flow
  - drag card between columns
