// Student play API client. Uses the shared fetch helper.
// NOTE: the X-Dev-Role header is a dev-only shim so the student app authenticates as a
// student against the dev backend (no Supabase JWT yet). Real auth arrives in M3.
import { apiFetch } from "@syllabusslayer/shared";

import type { AnswerResult, FinishResult, StartResponse } from "./types";

const DEV_HEADERS = { "X-Dev-Role": "student" };

export function startPlay(campaignId: string): Promise<StartResponse> {
  return apiFetch<StartResponse>(`/student/play/${campaignId}/start`, {
    method: "POST",
    headers: DEV_HEADERS,
  });
}

export interface AnswerBody {
  encounter_id: string;
  question_id: string;
  answer: unknown;
  time_ms?: number;
}

export function submitAnswer(sessionId: string, body: AnswerBody): Promise<AnswerResult> {
  return apiFetch<AnswerResult>(`/student/play/${sessionId}/answer`, {
    method: "POST",
    headers: DEV_HEADERS,
    body: JSON.stringify(body),
  });
}

export function finishPlay(sessionId: string): Promise<FinishResult> {
  return apiFetch<FinishResult>(`/student/play/${sessionId}/finish`, {
    method: "POST",
    headers: DEV_HEADERS,
  });
}
