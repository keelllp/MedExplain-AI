"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { FileText, MessageSquare, Paperclip, Plus, Send, Sparkles } from "lucide-react";

import { Alert, Badge, Button, Card, Spinner } from "@/components/ui";
import { ApiError } from "@/lib/api";
import * as api from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { ChatCitation, ChatMessage, ChatSession } from "@/lib/types";
import { cn } from "@/lib/utils";

type Bubble = ChatMessage & { refused?: boolean; pending?: boolean };

function Center() {
  return (
    <div className="flex justify-center py-16">
      <Spinner className="h-6 w-6 text-ink-faint" />
    </div>
  );
}

export default function ChatPage() {
  // useSearchParams must sit under a Suspense boundary in the app router.
  return (
    <Suspense fallback={<Center />}>
      <ChatInner />
    </Suspense>
  );
}

function ChatInner() {
  const { user, loading } = useRequireAuth();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  // A report_id in the URL starts a new chat scoped to that report.
  const reportParam = Number(searchParams.get("report_id"));
  const initialReportId = Number.isFinite(reportParam) && reportParam > 0 ? reportParam : null;

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [scopedReportId, setScopedReportId] = useState<number | null>(initialReportId);
  const [messages, setMessages] = useState<Bubble[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Attaching a file uploads it as a report, analyzes it, then scopes a fresh chat to it.
  const [attaching, setAttaching] = useState<{ name: string; phase: "uploading" | "analyzing"; progress: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const sessionsQuery = useQuery({
    queryKey: ["chat-sessions"],
    queryFn: () => api.listChatSessions(50, 0),
    enabled: !!user,
  });

  const historyQuery = useQuery({
    queryKey: ["chat-messages", sessionId],
    queryFn: () => api.getChatMessages(sessionId!),
    enabled: !!user && sessionId != null,
  });

  // Hydrate the thread from the server when an existing session is opened.
  useEffect(() => {
    if (sessionId != null && historyQuery.data) setMessages(historyQuery.data.items);
  }, [sessionId, historyQuery.data]);

  // The scoped report (for a friendly header badge when starting a report chat).
  const scopedReport = useQuery({
    queryKey: ["report", scopedReportId],
    queryFn: () => api.getReport(scopedReportId!),
    enabled: !!user && sessionId == null && scopedReportId != null,
  });

  const activeSession = useMemo<ChatSession | undefined>(
    () => sessionsQuery.data?.items.find((s) => s.id === sessionId),
    [sessionsQuery.data, sessionId],
  );

  const send = useMutation({
    mutationFn: (text: string) =>
      api.postChat({
        message: text,
        session_id: sessionId ?? undefined,
        // report scoping only applies when creating a brand-new session.
        report_id: sessionId == null ? scopedReportId ?? undefined : undefined,
      }),
    onMutate: (text: string) => {
      setError(null);
      setMessages((m) => [
        ...m,
        { id: -Date.now(), role: "user", content: text, citations: [], created_at: "" },
      ]);
    },
    onSuccess: (resp) => {
      setMessages((m) => [
        ...m,
        {
          id: resp.message_id,
          role: "assistant",
          content: resp.answer,
          citations: resp.citations,
          created_at: "",
          refused: resp.refused,
        },
      ]);
      if (sessionId == null) setSessionId(resp.session_id);
      // Refresh the sidebar (new session / updated ordering + title).
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
    onError: (err: unknown) => {
      // Drop the optimistic user bubble and surface a friendly reason.
      setMessages((m) => m.filter((x) => x.id >= 0));
      const msg =
        err instanceof ApiError
          ? err.status === 409
            ? "That report isn't analyzed yet — open it and run analysis first."
            : err.message
          : "Something went wrong. Please try again.";
      setError(msg);
    },
  });

  // Auto-scroll to the newest message.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, send.isPending]);

  if (loading || !user) return <Center />;

  function openSession(id: number) {
    setMessages([]);
    setScopedReportId(null);
    setError(null);
    setSessionId(id);
  }

  function newChat(reportId: number | null = null) {
    setMessages([]);
    setError(null);
    setScopedReportId(reportId);
    setSessionId(null);
  }

  function submit() {
    const text = draft.trim();
    if (!text || send.isPending || attaching) return;
    setDraft("");
    send.mutate(text);
  }

  // Attach a report file: upload → analyze → poll → scope a new chat to it. Runs to
  // completion in this click handler (no mount/unmount cancel ref needed).
  async function onAttachFile(file: File) {
    setError(null);
    if (file.size > 20 * 1024 * 1024) {
      setError("File exceeds the 20 MB limit.");
      return;
    }
    if (file.type && !["application/pdf", "image/jpeg", "image/png"].includes(file.type)) {
      setError("Unsupported file type. Attach a PDF, JPG, or PNG.");
      return;
    }
    setAttaching({ name: file.name, phase: "uploading", progress: 0 });
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("report_type", "other");
      const uploaded = await api.uploadReport(form);

      setAttaching({ name: file.name, phase: "analyzing", progress: 0 });
      await api.analyzeReport(uploaded.report_id);
      for (let attempt = 0; attempt < 200; attempt++) {
        const detail = await api.getReport(uploaded.report_id);
        setAttaching({ name: file.name, phase: "analyzing", progress: detail.progress });
        if (detail.status === "analyzed") break;
        if (detail.status === "failed") {
          setAttaching(null);
          setError("Couldn't read that file. Try a clearer PDF or image.");
          return;
        }
        await new Promise((res) => setTimeout(res, 1500));
      }
      // Scope a fresh chat to the new report (whether it finished or is still finishing).
      setAttaching(null);
      newChat(uploaded.report_id);
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    } catch (err) {
      setAttaching(null);
      setError(err instanceof ApiError ? err.message : "Couldn't attach that file.");
    }
  }

  const scopeBadge = (() => {
    if (sessionId == null && scopedReportId != null) {
      return scopedReport.data ? `About: ${scopedReport.data.title}` : "About a report";
    }
    if (activeSession?.report_id != null) return "Report chat";
    return "General chat";
  })();

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-3xl font-semibold leading-tight text-ink sm:text-4xl">
          Chat
        </h1>
        <p className="max-w-2xl text-ink-muted">
          Ask educational questions about your results and get hedged, source-cited answers. I
          can&apos;t diagnose, prescribe, or give dosages.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        {/* Sessions sidebar */}
        <aside className="flex flex-col gap-3">
          <Button onClick={() => newChat(null)} className="w-full">
            <Plus size={16} aria-hidden /> New chat
          </Button>
          <Card className="overflow-hidden">
            <div className="border-b border-line px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Recent
            </div>
            <div className="max-h-[55vh] divide-y divide-line overflow-y-auto">
              {sessionsQuery.isLoading ? (
                <div className="px-4 py-6 text-center">
                  <Spinner className="h-5 w-5 text-ink-faint" />
                </div>
              ) : sessionsQuery.data && sessionsQuery.data.items.length > 0 ? (
                sessionsQuery.data.items.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => openSession(s.id)}
                    className={cn(
                      "flex w-full items-center gap-2 px-4 py-3 text-left text-sm transition-colors",
                      s.id === sessionId
                        ? "bg-brand-tint text-brand-strong"
                        : "text-ink-muted hover:bg-surface-sunken hover:text-ink",
                    )}
                  >
                    {s.report_id != null ? (
                      <FileText size={14} className="shrink-0 text-ink-faint" aria-hidden />
                    ) : (
                      <MessageSquare size={14} className="shrink-0 text-ink-faint" aria-hidden />
                    )}
                    <span className="truncate">{s.title}</span>
                  </button>
                ))
              ) : (
                <p className="px-4 py-6 text-center text-sm text-ink-faint">No chats yet.</p>
              )}
            </div>
          </Card>
        </aside>

        {/* Chat panel */}
        <Card className="flex h-[68vh] min-h-[26rem] flex-col">
          <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
            <div className="flex items-center gap-2 text-sm font-medium text-ink">
              <Sparkles size={16} className="text-brand" aria-hidden />
              {activeSession?.title ?? (sessionId == null ? "New chat" : "Chat")}
            </div>
            <Badge
              className={
                scopeBadge === "General chat"
                  ? "bg-surface-sunken text-ink-muted"
                  : "bg-brand-tint text-brand"
              }
            >
              {scopeBadge}
            </Badge>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
            {historyQuery.isLoading && sessionId != null ? (
              <Center />
            ) : messages.length === 0 ? (
              <EmptyThread scoped={scopedReportId != null} />
            ) : (
              messages.map((m) => <MessageBubble key={m.id} message={m} />)
            )}
            {send.isPending && <ThinkingBubble />}
          </div>

          {/* Composer */}
          <div className="border-t border-line px-4 py-3">
            {error && <Alert className="mb-2 text-[13px]">{error}</Alert>}
            {attaching && (
              <div className="mb-2 flex items-center gap-2 rounded-xl border border-line bg-surface-sunken/60 px-3 py-2 text-[13px] text-ink-muted">
                <Spinner className="h-4 w-4 text-brand" />
                <span className="truncate">
                  {attaching.phase === "uploading" ? "Uploading" : "Reading"}{" "}
                  <span className="font-medium text-ink">{attaching.name}</span>
                  {attaching.phase === "analyzing" ? ` — analyzing ${attaching.progress}%` : "…"}
                </span>
              </div>
            )}
            <div className="flex items-end gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                className="sr-only"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = ""; // allow re-picking the same file
                  if (f) onAttachFile(f);
                }}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={!!attaching || send.isPending}
                aria-label="Attach a report (PDF or image)"
                title="Attach a report (PDF or image)"
                className="h-11 w-11 shrink-0 rounded-xl p-0"
              >
                <Paperclip size={18} aria-hidden />
              </Button>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submit();
                  }
                }}
                rows={1}
                disabled={!!attaching}
                placeholder={
                  attaching ? "Reading your report…" : "Ask about a result, or attach a report with the clip…"
                }
                className={cn(
                  "max-h-32 min-h-[2.75rem] flex-1 resize-none rounded-xl border border-line-strong bg-surface px-3.5 py-2.5 text-sm text-ink",
                  "placeholder:text-ink-faint shadow-sm outline-none transition focus:border-brand focus:shadow-focus",
                  "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-muted",
                )}
              />
              <Button
                onClick={submit}
                disabled={!draft.trim() || send.isPending || !!attaching}
                aria-label="Send"
              >
                <Send size={16} aria-hidden />
              </Button>
            </div>
            <p className="mt-2 px-1 text-[11px] text-ink-faint">
              Educational only — not a diagnosis. Consult a licensed healthcare professional for
              medical advice.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Bubble }) {
  const isUser = message.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div
        className={cn(
          "max-w-[85%] space-y-2 rounded-2xl rounded-bl-md border px-4 py-3 text-sm leading-relaxed shadow-sm",
          message.refused
            ? "border-alert/25 bg-alert-tint text-ink"
            : "border-line bg-surface-sunken/60 text-ink",
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {message.citations.length > 0 && <Citations citations={message.citations} />}
      </div>
    </div>
  );
}

function Citations({ citations }: { citations: ChatCitation[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 border-t border-line pt-2">
      <span className="text-[11px] font-medium uppercase tracking-wide text-ink-faint">Sources</span>
      {citations.map((c, i) => (
        <span
          key={`${c.chunk_id}-${i}`}
          title={c.chunk_id}
          className="inline-flex items-center gap-1 rounded-full bg-brand-tint px-2 py-0.5 text-[11px] font-medium text-brand"
        >
          <FileText size={11} aria-hidden />
          {c.doc}
        </span>
      ))}
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-line bg-surface-sunken/60 px-4 py-3 text-sm text-ink-muted shadow-sm">
        <Spinner className="h-4 w-4 text-brand" />
        <span>Thinking… (the offline model can be slow)</span>
      </div>
    </div>
  );
}

function EmptyThread({ scoped }: { scoped: boolean }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-tint text-brand">
        <MessageSquare size={24} strokeWidth={1.75} aria-hidden />
      </div>
      <p className="mt-4 max-w-sm text-sm text-ink-muted">
        {scoped
          ? "Ask a question about this report — for example, what a flagged marker measures or what an out-of-range value can generally be associated with."
          : "Ask an educational question about a lab marker, or attach a report with the clip to ask about your own results."}
      </p>
    </div>
  );
}
