"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { createId, initialData, moveCard as moveCardLocal, type BoardData } from "@/lib/kanban";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type BackendBoard = {
  columns: {
    id: number;
    key: string;
    title: string;
    cardIds: number[];
  }[];
  cards: Record<
    string,
    {
      id: number;
      title: string;
      details: string;
      columnId: number;
    }
  >;
};

type AIChatResponse = {
  ok: boolean;
  response: string;
  board: BackendBoard;
  applied_operations: string[];
  parse_error: boolean;
};

type SessionPayload = {
  authenticated: boolean;
  user: { id: number; username: string; email: string } | null;
};

const toUiCardId = (id: number) => `card-${id}`;

const toUiBoard = (backendBoard: BackendBoard) => {
  const columnIdByUiId: Record<string, number> = {};
  const cardIdByUiId: Record<string, number> = {};

  for (const column of backendBoard.columns) {
    columnIdByUiId[column.key] = column.id;
  }

  const cards: BoardData["cards"] = {};
  for (const card of Object.values(backendBoard.cards)) {
    const uiCardId = toUiCardId(card.id);
    cardIdByUiId[uiCardId] = card.id;
    cards[uiCardId] = {
      id: uiCardId,
      title: card.title,
      details: card.details,
    };
  }

  const columns = backendBoard.columns.map((column) => ({
    id: column.key,
    title: column.title,
    cardIds: column.cardIds
      .map((id) => toUiCardId(id))
      .filter((uiCardId) => Boolean(cards[uiCardId])),
  }));

  return {
    board: { columns, cards },
    maps: {
      columnIdByUiId,
      cardIdByUiId,
    },
  };
};

export const KanbanBoard = () => {
  const [board, setBoard] = useState<BoardData>(() => initialData);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [usesBackend, setUsesBackend] = useState(false);
  const [columnIdByUiId, setColumnIdByUiId] = useState<Record<string, number>>({});
  const [cardIdByUiId, setCardIdByUiId] = useState<Record<string, number>>({});
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isChatSending, setIsChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [boardLoadError, setBoardLoadError] = useState<string | null>(null);

  const applyBackendBoard = useCallback((backendBoard: BackendBoard) => {
    const { board: nextBoard, maps } = toUiBoard(backendBoard);
    setBoard(nextBoard);
    setColumnIdByUiId(maps.columnIdByUiId);
    setCardIdByUiId(maps.cardIdByUiId);
  }, []);

  const loadBoardFromBackend = useCallback(async () => {
    const response = await fetch("/api/board");
    if (!response.ok) {
      throw new Error("Unable to fetch board");
    }
    const backendBoard = (await response.json()) as BackendBoard;
    applyBackendBoard(backendBoard);
    setUsesBackend(true);
    setBoardLoadError(null);
  }, [applyBackendBoard]);

  useEffect(() => {
    let isMounted = true;
    void (async () => {
      try {
        const sessionResponse = await fetch("/api/auth/session");
        if (!sessionResponse.ok) {
          throw new Error("Unable to check session");
        }
        const session = (await sessionResponse.json()) as SessionPayload;
        if (!session.authenticated) {
          if (isMounted) {
            setUsesBackend(false);
            setBoardLoadError("Authentication required. Please sign in.");
          }
          return;
        }
        await loadBoardFromBackend();
      } catch {
        if (isMounted) {
          setUsesBackend(false);
          setBoardLoadError(
            "Backend unavailable. Local fallback mode is active for UI-only work."
          );
        }
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [loadBoardFromBackend]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board.cards, [board.cards]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const mutateBoard = useCallback(
    async (
      method: string,
      url: string,
      body: object | null,
      options: { refetchOnSuccess?: boolean } = {}
    ) => {
      try {
        const response = await fetch(url, {
          method,
          headers: body !== null ? { "Content-Type": "application/json" } : undefined,
          body: body !== null ? JSON.stringify(body) : undefined,
        });
        if (!response.ok) {
          await loadBoardFromBackend();
          return;
        }
        if (options.refetchOnSuccess) {
          await loadBoardFromBackend();
        }
      } catch {
        await loadBoardFromBackend().catch(() => {});
      }
    },
    [loadBoardFromBackend]
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    if (usesBackend) {
      const activeUiCardId = active.id as string;
      const backendCardId = cardIdByUiId[activeUiCardId];
      if (!backendCardId) {
        return;
      }

      const overUiId = over.id as string;
      const sourceColumn = board.columns.find((column) =>
        column.cardIds.includes(activeUiCardId)
      );
      if (!sourceColumn) {
        return;
      }

      const targetColumnUiId = columnIdByUiId[overUiId]
        ? overUiId
        : board.columns.find((column) => column.cardIds.includes(overUiId))?.id;

      if (!targetColumnUiId) {
        return;
      }

      const targetBackendColumnId = columnIdByUiId[targetColumnUiId];
      if (!targetBackendColumnId) {
        return;
      }

      const targetColumn = board.columns.find((column) => column.id === targetColumnUiId);
      if (!targetColumn) {
        return;
      }

      const sourceIndex = sourceColumn.cardIds.indexOf(activeUiCardId);
      const overIndex = targetColumn.cardIds.indexOf(overUiId);
      const targetPosition =
        overIndex === -1
          ? targetColumn.cardIds.filter((id) => id !== activeUiCardId).length
          : overIndex;

      setBoard((prev) => ({
        ...prev,
        columns: moveCardLocal(prev.columns, activeUiCardId, overUiId),
      }));

      void mutateBoard("POST", `/api/cards/${backendCardId}/move`, {
        target_column_id: targetBackendColumnId,
        target_position:
          sourceColumn.id === targetColumnUiId && sourceIndex === overIndex
            ? sourceIndex
            : targetPosition,
      });
      return;
    }

    setBoard((prev) => ({
      ...prev,
      columns: moveCardLocal(prev.columns, active.id as string, over.id as string),
    }));
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    setBoard((prev) => ({
      ...prev,
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    }));

    if (usesBackend) {
      const backendColumnId = columnIdByUiId[columnId];
      if (!backendColumnId) {
        return;
      }
      void mutateBoard("PATCH", `/api/columns/${backendColumnId}`, { title });
    }
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    if (usesBackend) {
      const backendColumnId = columnIdByUiId[columnId];
      if (!backendColumnId) {
        return;
      }
      void mutateBoard(
        "POST",
        `/api/columns/${backendColumnId}/cards`,
        { title, details },
        { refetchOnSuccess: true }
      );
      return;
    }

    const id = createId("card");
    setBoard((prev) => ({
      ...prev,
      cards: {
        ...prev.cards,
        [id]: { id, title, details: details || "No details yet." },
      },
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    }));
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    setBoard((prev) => ({
      ...prev,
      cards: Object.fromEntries(
        Object.entries(prev.cards).filter(([id]) => id !== cardId)
      ),
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: column.cardIds.filter((id) => id !== cardId) }
          : column
      ),
    }));

    if (usesBackend) {
      const backendCardId = cardIdByUiId[cardId];
      if (!backendCardId) {
        return;
      }
      void mutateBoard("DELETE", `/api/cards/${backendCardId}`, null);
    }
  };

  const handleLogout = () => {
    window.location.href = "/logout";
  };

  const handleChatSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!usesBackend || isChatSending) {
      return;
    }
    const trimmed = chatInput.trim();
    if (!trimmed) {
      return;
    }

    setChatError(null);
    setChatInput("");
    setIsChatSending(true);
    setChatMessages((prev) => [...prev, { role: "user", content: trimmed }]);

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });
      if (!response.ok) {
        throw new Error("AI request failed");
      }
      const payload = (await response.json()) as AIChatResponse;
      if (payload.ok) {
        setChatMessages((prev) => [
          ...prev,
          { role: "assistant", content: payload.response },
        ]);
        applyBackendBoard(payload.board);
      } else {
        throw new Error("AI response was not successful");
      }
    } catch {
      setChatError("Unable to reach AI service right now.");
    } finally {
      setIsChatSending(false);
    }
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-6 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                One board. Five columns. Zero clutter.
              </p>
              <button
                type="button"
                onClick={handleLogout}
                className="mt-4 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.15em] text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
              >
                Log out
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
          {boardLoadError ? (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {boardLoadError}
            </p>
          ) : null}
        </header>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCorners}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
              <section className="grid gap-6 lg:grid-cols-5">
                {board.columns.map((column) => (
                  <KanbanColumn
                    key={column.id}
                    column={column}
                    cards={column.cardIds.map((cardId) => board.cards[cardId])}
                    onRename={handleRenameColumn}
                    onAddCard={handleAddCard}
                    onDeleteCard={handleDeleteCard}
                  />
                ))}
              </section>
              <DragOverlay>
                {activeCard ? (
                  <div className="w-[260px]">
                    <KanbanCardPreview card={activeCard} />
                  </div>
                ) : null}
              </DragOverlay>
            </DndContext>
          </div>

          <aside className="rounded-3xl border border-[var(--stroke)] bg-white p-5 shadow-[var(--shadow)]">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-display text-lg font-semibold text-[var(--navy-dark)]">
                AI Assistant
              </h2>
              <span className="rounded-full bg-[var(--surface)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--gray-text)]">
                Live
              </span>
            </div>
            <p className="mt-2 text-sm text-[var(--gray-text)]">
              Ask for card updates or planning help. Board changes apply automatically.
            </p>

            <div className="mt-4 h-[420px] overflow-y-auto rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-3">
              {chatMessages.length === 0 ? (
                <p className="text-sm text-[var(--gray-text)]">
                  Try: &quot;Add a card to Backlog for API docs.&quot;
                </p>
              ) : (
                <div className="space-y-3">
                  {chatMessages.map((message, index) => (
                    <div
                      key={`${message.role}-${index}`}
                      className={
                        message.role === "user"
                          ? "ml-auto max-w-[92%] rounded-2xl bg-[var(--primary-blue)] px-3 py-2 text-sm text-white"
                          : "max-w-[92%] rounded-2xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)]"
                      }
                    >
                      {message.content}
                    </div>
                  ))}
                  {isChatSending ? (
                    <div className="max-w-[92%] rounded-2xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)]">
                      Thinking...
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            <form onSubmit={handleChatSubmit} className="mt-4 space-y-3">
              <textarea
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="Ask the assistant..."
                rows={3}
                className="w-full resize-none rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              />
              {chatError ? (
                <p className="text-xs font-semibold text-red-600">{chatError}</p>
              ) : null}
              <button
                type="submit"
                disabled={isChatSending || !chatInput.trim() || !usesBackend}
                className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Send
              </button>
            </form>
          </aside>
        </section>
      </main>
    </div>
  );
};
