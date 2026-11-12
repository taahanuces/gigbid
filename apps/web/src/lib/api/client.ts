import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const client = createClient<paths>({ baseUrl: API_URL });

client.use({
  async onRequest({ request }) {
    if (typeof window !== "undefined") {
      const accessToken = window.localStorage.getItem("gigbid_token");
      if (accessToken) request.headers.set("Authorization", `Bearer ${accessToken}`);
    }
    return request;
  },
});

export type Job = components["schemas"]["JobSummary"];
export type InboxJob = components["schemas"]["InboxJob"];
export type RunState = components["schemas"]["RunResponse"];
export type CheckpointHistory = components["schemas"]["CheckpointHistoryResponse"];
export type CheckpointReplay = components["schemas"]["CheckpointReplayResponse"];
export type Health = components["schemas"]["HealthResponse"];
export type ApprovalInput = components["schemas"]["ApprovalRequest"];
export type MemoryItem = components["schemas"]["MemoryItem"];
export type Analytics = components["schemas"]["AnalyticsResponse"];
export type Pipeline = components["schemas"]["PipelineResponse"];
export type Messages = components["schemas"]["MessagesResponse"];
export type ConversationRun = components["schemas"]["ConversationRunResponse"];
export type Profile = components["schemas"]["ProfileResponse"];
export type ProfileSettings = components["schemas"]["ProfileSettings"];
export type RunNodeEvent = { node?: string; status?: string; action?: string; passed?: boolean };
export type ParagraphRegeneration = components["schemas"]["ParagraphRegenerateResponse"];
export type PortfolioEvidence = components["schemas"]["EvidenceItem"];
type RunStreamHandlers = {
  onNode: (event: RunNodeEvent) => void;
  onStatus: (status: string) => void;
};

function failure(error: unknown, response: Response): Error {
  if (typeof error === "object" && error !== null && "detail" in error) {
    return new Error(String(error.detail));
  }
  return new Error(response.statusText || "Request failed");
}

export async function login(email: string, password: string): Promise<void> {
  const { data, error, response } = await client.POST("/api/auth/login", {
    body: { email, password },
  });
  if (error || !data) throw failure(error, response);
  window.localStorage.setItem("gigbid_token", data.access_token);
}

export const api = {
  async health(): Promise<Health> {
    const { data, error, response } = await client.GET("/health");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async jobs(): Promise<Job[]> {
    const { data, error, response } = await client.GET("/api/jobs");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async inbox(): Promise<InboxJob[]> {
    const { data, error, response } = await client.GET("/api/jobs/ranked/inbox");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async job(id: string): Promise<Job> {
    const { data, error, response } = await client.GET("/api/jobs/{job_id}", {
      params: { path: { job_id: id } },
    });
    if (error || !data) throw failure(error, response);
    return data;
  },
  async analyze(id: string): Promise<RunState> {
    const { data, error, response } = await client.POST("/api/jobs/{job_id}/analyze", {
      params: { path: { job_id: id } },
      body: {},
    });
    if (error || !data) throw failure(error, response);
    return data;
  },
  async run(threadId: string): Promise<RunState> {
    const { data, error, response } = await client.GET("/api/runs/{thread_id}", {
      params: { path: { thread_id: threadId } },
    });
    if (error || !data) throw failure(error, response);
    return data;
  },
  async streamRunEvents(
    threadId: string,
    handlers: RunStreamHandlers,
    signal: AbortSignal,
  ): Promise<void> {
    const accessToken = window.localStorage.getItem("gigbid_token");
    const response = await fetch(`${API_URL}/api/runs/${encodeURIComponent(threadId)}/events`, {
      headers: {
        Accept: "text/event-stream",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      signal,
    });
    if (!response.ok || !response.body) throw new Error("Run event stream is unavailable");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const lines = frame.split("\n");
        const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
        const data = lines
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (!data) continue;
        const payload: unknown = JSON.parse(data);
        if (eventName === "node" && typeof payload === "object" && payload !== null) {
          handlers.onNode(payload as RunNodeEvent);
        }
        if (eventName === "status" && typeof payload === "object" && payload !== null) {
          const status = (payload as { status?: unknown }).status;
          if (typeof status === "string") handlers.onStatus(status);
        }
      }
      if (done) return;
    }
  },
  async runHistory(threadId: string): Promise<CheckpointHistory> {
    const { data, error, response } = await client.GET("/api/runs/{thread_id}/history", {
      params: { path: { thread_id: threadId } },
    });
    if (error || !data) throw failure(error, response);
    return data;
  },
  async replayCheckpoint(threadId: string, checkpointId: string): Promise<CheckpointReplay> {
    const { data, error, response } = await client.GET(
      "/api/runs/{thread_id}/replay/{checkpoint_id}",
      { params: { path: { thread_id: threadId, checkpoint_id: checkpointId } } },
    );
    if (error || !data) throw failure(error, response);
    return data;
  },
  async approval(threadId: string, input: ApprovalInput): Promise<RunState> {
    const { data, error, response } = await client.POST("/api/runs/{thread_id}/approval", {
      params: { path: { thread_id: threadId } },
      body: input,
    });
    if (error || !data) throw failure(error, response);
    return data;
  },
  async regenerateParagraph(threadId: string, paragraphIndex: number): Promise<ParagraphRegeneration> {
    const { data, error, response } = await client.POST(
      "/api/runs/{thread_id}/regenerate-paragraph",
      {
        params: { path: { thread_id: threadId } },
        body: { paragraph_index: paragraphIndex },
      },
    );
    if (error || !data) throw failure(error, response);
    return data;
  },
  async memories(): Promise<MemoryItem[]> {
    const { data, error, response } = await client.GET("/api/memories");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async profile(): Promise<Profile> {
    const { data, error, response } = await client.GET("/api/profile");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async saveProfile(settings: ProfileSettings): Promise<Profile> {
    const { data, error, response } = await client.PUT("/api/profile", { body: settings });
    if (error || !data) throw failure(error, response);
    return data;
  },
  async portfolio(): Promise<PortfolioEvidence[]> {
    const { data, error, response } = await client.GET("/api/portfolio");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async uploadPortfolio(
    file: File,
    persona: string,
    skills: string,
  ): Promise<PortfolioEvidence[]> {
    const form = new FormData();
    form.set("file", file);
    form.set("persona", persona);
    form.set("skills", skills);
    const accessToken = window.localStorage.getItem("gigbid_token");
    const response = await fetch(`${API_URL}/api/portfolio/upload`, {
      method: "POST",
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      body: form,
    });
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => ({}));
      throw failure(body, response);
    }
    return await response.json() as PortfolioEvidence[];
  },
  async deletePortfolio(evidenceId: string): Promise<void> {
    const { error, response } = await client.DELETE("/api/portfolio/{evidence_id}", {
      params: { path: { evidence_id: evidenceId } },
    });
    if (error) throw failure(error, response);
  },
  async analytics(): Promise<Analytics> {
    const { data, error, response } = await client.GET("/api/analytics");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async pipeline(): Promise<Pipeline> {
    const { data, error, response } = await client.GET("/api/pipeline");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async messages(): Promise<Messages> {
    const { data, error, response } = await client.GET("/api/messages");
    if (error || !data) throw failure(error, response);
    return data;
  },
  async startConversation(conversationId: string, inboundMessage: string): Promise<ConversationRun> {
    const { data, error, response } = await client.POST("/api/conversations/{conversation_id}/draft", {
      params: { path: { conversation_id: conversationId } },
      body: { inbound_message: inboundMessage, free_slots: [] },
    });
    if (error || !data) throw failure(error, response);
    return data;
  },
  async approveConversation(threadId: string, input: ApprovalInput): Promise<ConversationRun> {
    const { data, error, response } = await client.POST("/api/conversations/runs/{thread_id}/approval", {
      params: { path: { thread_id: threadId } },
      body: input,
    });
    if (error || !data) throw failure(error, response);
    return data;
  },
  async deleteMemory(memory: MemoryItem): Promise<void> {
    const { error, response } = await client.DELETE("/api/memories/{kind}/{key}", {
      params: { path: { kind: memory.kind, key: memory.key } },
    });
    if (error) throw failure(error, response);
  },
};
