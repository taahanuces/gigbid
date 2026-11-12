"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";
import { api, type ConversationRun, type Messages } from "@/lib/api/client";

export default function MessagesPage() {
  const [messages, setMessages] = useState<Messages | null>(null);
  const [selected, setSelected] = useState(0);
  const [run, setRun] = useState<ConversationRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api.messages().then(setMessages).catch((caught: Error) => setError(caught.message)); }, []);
  const thread = messages?.threads[selected];
  const draft = run?.state.draft as { intent?: string; reply?: string; proposed_slots?: string[]; risk_signals?: string[] } | undefined;
  const lastInbound = thread?.messages.filter((message) => message.direction === "inbound").at(-1);

  async function draftReply() {
    if (!thread || !lastInbound?.body) return;
    setBusy(true);
    try {
      setRun(await api.startConversation(thread.conversation_id, String(lastInbound.body)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Reply drafting failed");
    } finally {
      setBusy(false);
    }
  }

  async function approveReply() {
    if (!run) return;
    setBusy(true);
    try {
      setRun(await api.approveConversation(run.thread_id, { action: "approve" }));
      setMessages(await api.messages());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Reply approval failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader eyebrow="Client liaison" title="Messages" description="Marketplace replies are visible here; suggested responses still require an approval interrupt." />
      {error ? <p className="error-message">{error}</p> : null}
      <div className="messages-layout">
        <section className="section-card thread-list"><span className="eyebrow">Threads</span>{messages?.threads.map((item, index) => <button className={`thread ${index === selected ? "active" : ""}`} key={item.conversation_id} onClick={() => setSelected(index)}><span className="avatar">SC</span><div><strong>{item.client_name}</strong><small>{item.messages.length} messages</small></div></button>)}</section>
        <section className="section-card">{thread ? <><span className="eyebrow">Conversation</span><h2>{thread.client_name}</h2><div className="message-stack">{thread.messages.map((message, index) => <article className={`message-bubble ${String(message.direction)}`} key={String(message.message_id ?? index)}><small>{String(message.direction)}</small><p>{String(message.body ?? "")}</p></article>)}</div>{draft ? <div className="reply-review"><span className="eyebrow">{draft.intent?.replaceAll("_", " ")}</span><h3>Suggested reply</h3>{draft.risk_signals?.length ? <p className="error-message">Blocked: {draft.risk_signals.join(", ")}</p> : <><p>{draft.reply}</p>{draft.proposed_slots?.length ? <ul>{draft.proposed_slots.map((slot) => <li key={slot}>{slot}</li>)}</ul> : null}<button className="button primary" disabled={busy || run?.status !== "awaiting_approval"} onClick={approveReply}>{run?.status === "sent" ? "Sent" : "Approve and send"}</button></>}</div> : <div className="empty-state"><strong>Reply requires review</strong><p>Draft a response from the latest inbound message. Nothing is sent automatically.</p><button className="button primary" disabled={busy || !lastInbound} onClick={draftReply}>{busy ? "Drafting…" : "Draft suggested reply"}</button></div>}</> : <div className="empty-state"><strong>No reply to review</strong><p>Client messages will appear after a simulator proposal receives a reply.</p></div>}</section>
      </div>
    </AppShell>
  );
}

