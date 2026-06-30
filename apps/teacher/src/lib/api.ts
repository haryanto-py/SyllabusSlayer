// Teacher console API client. X-Dev-Role: teacher is a dev shim until Supabase auth (M3-T6).
import { apiFetch } from "@syllabusslayer/shared";

const H = { "X-Dev-Role": "teacher" };

export interface ClassOut {
  id: string;
  name: string;
  join_code: string;
  student_count: number;
}
export interface RosterStudent {
  id: string;
  display_name: string;
  email: string | null;
}
export interface ClassDetail {
  id: string;
  name: string;
  join_code: string;
  roster: RosterStudent[];
}
export interface CampaignSummary {
  id: string;
  title: string;
  status: string;
}
export interface AssignmentOut {
  id: string;
  campaign_id: string;
  campaign_title: string;
  class_id: string;
  due_at: string | null;
}

export interface ReviewOption {
  optionId: string;
  text: string;
}
export interface ReviewQuestion {
  questionId: string;
  questionType: string;
  bloomLevel: string;
  difficulty: string;
  prompt: string;
  explanation: string;
  sourceQuote?: string | null;
  sourceChunkIds?: string[];
  sourcePage?: number | null;
  hint?: string | null;
  options?: ReviewOption[] | null;
  correctOptionIds?: string[] | null;
  correctBoolean?: boolean | null;
  acceptedAnswers?: string[] | null;
  caseSensitive?: boolean | null;
  orderedItems?: { itemId: string; text: string; order: number }[] | null;
  matchPairs?: { pairId: string; left: string; right: string }[] | null;
}
export interface ReviewEncounter {
  encounterId: string;
  title: string;
  kind: string;
  subTopic: string;
  questions: ReviewQuestion[];
}
export interface ReviewAct {
  actId: string;
  title: string;
  syllabusTopic: string;
  encounters: ReviewEncounter[];
}
export interface ReviewGame {
  campaignId: string;
  title: string;
  description: string;
  acts: ReviewAct[];
}
export interface CampaignDetail {
  id: string;
  title: string;
  status: string;
  game: ReviewGame;
}

export interface Analytics {
  campaign_id: string;
  class_id: string;
  students: {
    student_id: string;
    name: string;
    attempts: number;
    correct: number;
    accuracy: number;
    best_score: number;
    completed: boolean;
  }[];
  topics: { topic: string; attempts: number; correct: number; accuracy: number }[];
  items: { question_id: string; prompt: string; attempts: number; p_value: number }[];
  summary: { roster_size: number; started: number; completed: number; avg_accuracy: number };
}

export const teacher = {
  listClasses: () => apiFetch<ClassOut[]>("/teacher/classes", { headers: H }),
  createClass: (name: string) =>
    apiFetch<ClassOut>("/teacher/classes", {
      method: "POST",
      headers: H,
      body: JSON.stringify({ name }),
    }),
  classDetail: (id: string) => apiFetch<ClassDetail>(`/teacher/classes/${id}`, { headers: H }),
  listCampaigns: () => apiFetch<CampaignSummary[]>("/teacher/campaigns", { headers: H }),
  getCampaign: (id: string) => apiFetch<CampaignDetail>(`/teacher/campaigns/${id}`, { headers: H }),
  listAssignments: (classId: string) =>
    apiFetch<AssignmentOut[]>(`/teacher/classes/${classId}/assignments`, { headers: H }),
  assign: (classId: string, campaignId: string) =>
    apiFetch<AssignmentOut>(`/teacher/classes/${classId}/assignments`, {
      method: "POST",
      headers: H,
      body: JSON.stringify({ campaign_id: campaignId }),
    }),
  editQuestion: (campaignId: string, questionId: string, q: ReviewQuestion) =>
    apiFetch(`/teacher/campaigns/${campaignId}/questions/${questionId}`, {
      method: "PUT",
      headers: H,
      body: JSON.stringify(q),
    }),
  publish: (campaignId: string) =>
    apiFetch<{ id: string; status: string }>(`/teacher/campaigns/${campaignId}/publish`, {
      method: "POST",
      headers: H,
    }),
  analytics: (campaignId: string, classId: string) =>
    apiFetch<Analytics>(
      `/teacher/campaigns/${campaignId}/analytics?class_id=${classId}`,
      { headers: H },
    ),
};
