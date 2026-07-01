// Supabase auth helpers (email + password). The app role (teacher/student) is stored in
// user_metadata at signup and read by the backend from the JWT.
import type { Session } from "@supabase/supabase-js";

import { supabase } from "./supabaseClient";

export type Role = "teacher" | "student";

export function signUp(email: string, password: string, role: Role) {
  return supabase.auth.signUp({ email, password, options: { data: { role } } });
}

export function signIn(email: string, password: string) {
  return supabase.auth.signInWithPassword({ email, password });
}

export function signOut() {
  return supabase.auth.signOut();
}

export async function getSession(): Promise<Session | null> {
  return (await supabase.auth.getSession()).data.session;
}

export function onAuthChange(cb: (session: Session | null) => void) {
  return supabase.auth.onAuthStateChange((_event, session) => cb(session)).data.subscription;
}

/** Auth headers for backend calls: the Supabase access token if signed in, else the dev shim. */
export async function authHeaders(devRole: Role): Promise<Record<string, string>> {
  const session = await getSession();
  if (session?.access_token) return { Authorization: `Bearer ${session.access_token}` };
  return { "X-Dev-Role": devRole };
}
