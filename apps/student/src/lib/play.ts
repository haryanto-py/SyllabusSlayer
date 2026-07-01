// Student play API client. Attaches the Supabase access token (or dev-role fallback).
import { apiFetch } from "@syllabusslayer/shared";
import { authHeaders } from "@syllabusslayer/shared/auth";

import type { AnswerResult, FinishResult, StartResponse } from "./types";

export async function startPlay(campaignId: string): Promise<StartResponse> {
  return apiFetch<StartResponse>(`/student/play/${campaignId}/start`, {
    method: "POST",
    headers: await authHeaders("student"),
  });
}

export interface AnswerBody {
  encounter_id: string;
  question_id: string;
  answer: unknown;
  time_ms?: number;
}

export async function submitAnswer(sessionId: string, body: AnswerBody): Promise<AnswerResult> {
  return apiFetch<AnswerResult>(`/student/play/${sessionId}/answer`, {
    method: "POST",
    headers: await authHeaders("student"),
    body: JSON.stringify(body),
  });
}

export async function finishPlay(sessionId: string): Promise<FinishResult> {
  return apiFetch<FinishResult>(`/student/play/${sessionId}/finish`, {
    method: "POST",
    headers: await authHeaders("student"),
  });
}

export async function joinClass(joinCode: string): Promise<{ id: string; name: string }> {
  return apiFetch(`/student/classes/join`, {
    method: "POST",
    headers: await authHeaders("student"),
    body: JSON.stringify({ join_code: joinCode }),
  });
}

export interface AssignmentItem {
  assignment_id: string;
  campaign_id: string;
  title: string;
  class_name: string;
  due_at: string | null;
}

export async function listAssignments(): Promise<AssignmentItem[]> {
  return apiFetch<AssignmentItem[]>(`/student/assignments`, {
    headers: await authHeaders("student"),
  });
}
