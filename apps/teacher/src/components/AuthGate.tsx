"use client";

import { useEffect, useState } from "react";

import {
  getSession,
  onAuthChange,
  type Role,
  signIn,
  signOut,
  signUp,
} from "@syllabusslayer/shared/auth";

type SessionT = Awaited<ReturnType<typeof getSession>>;

export default function AuthGate({ role, children }: { role: Role; children: React.ReactNode }) {
  const [session, setSession] = useState<SessionT | undefined>(undefined);

  useEffect(() => {
    getSession().then(setSession);
    const sub = onAuthChange(setSession);
    return () => sub.unsubscribe();
  }, []);

  if (session === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center text-zinc-400">Loading…</div>
    );
  }
  if (!session) return <LoginForm role={role} />;

  return (
    <>
      <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-2 text-sm text-zinc-400">
        <span className="truncate">{session.user.email}</span>
        <button
          onClick={() => signOut()}
          className="rounded border border-zinc-700 px-3 py-1 hover:bg-zinc-800"
        >
          Sign out
        </button>
      </header>
      {children}
    </>
  );
}

function LoginForm({ role }: { role: Role }) {
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const teacher = role === "teacher";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      if (mode === "up") {
        const { data, error } = await signUp(email, pw, role);
        if (error) throw error;
        if (!data.session) setMsg("Account created — check your email to confirm, then sign in.");
      } else {
        const { error } = await signIn(email, pw);
        if (error) throw error;
      }
    } catch (err) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-6 text-zinc-100">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6"
      >
        <h1 className="text-xl font-bold">
          SyllabusSlayer{" "}
          <span className={teacher ? "text-emerald-400" : "text-amber-400"}>
            {teacher ? "Teacher" : "Student"}
          </span>
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          {mode === "in" ? "Sign in" : "Create your account"}
        </p>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email"
          className="mt-4 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
        />
        <input
          type="password"
          required
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          placeholder="password"
          className="mt-2 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
        />
        <button
          disabled={busy}
          className={`mt-4 w-full rounded-lg px-4 py-2 font-semibold text-zinc-950 disabled:opacity-50 ${
            teacher ? "bg-emerald-500 hover:bg-emerald-400" : "bg-amber-500 hover:bg-amber-400"
          }`}
        >
          {busy ? "…" : mode === "in" ? "Sign in" : "Sign up"}
        </button>
        {msg && <p className="mt-3 text-xs text-amber-300">{msg}</p>}
        <button
          type="button"
          onClick={() => setMode(mode === "in" ? "up" : "in")}
          className="mt-3 w-full text-xs text-zinc-500 hover:text-zinc-300"
        >
          {mode === "in" ? "No account? Sign up" : "Have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
