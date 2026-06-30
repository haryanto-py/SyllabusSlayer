"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { type AssignmentItem, joinClass, listAssignments } from "@/lib/play";

export default function MyGames() {
  const [code, setCode] = useState("");
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  const load = () => listAssignments().then(setAssignments).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  const join = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    try {
      const c = await joinClass(code.trim());
      setMsg(`Joined ${c.name}`);
      setCode("");
      load();
    } catch {
      setMsg("No class with that code.");
    }
  };

  return (
    <div className="mt-8 w-full max-w-md">
      <form onSubmit={join} className="flex gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="CLASS CODE"
          className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900/70 px-4 py-3 text-center font-mono uppercase tracking-widest text-zinc-300 placeholder:text-zinc-600"
        />
        <button className="rounded-lg bg-amber-500/80 px-5 py-3 font-semibold text-zinc-950 hover:bg-amber-400">
          Join
        </button>
      </form>
      {msg && <p className="mt-2 text-center text-xs text-zinc-400">{msg}</p>}

      <h2 className="mt-6 text-left text-xs uppercase tracking-wide text-zinc-500">Your games</h2>
      <div className="mt-2 flex flex-col gap-2">
        {assignments.length === 0 && (
          <p className="text-sm text-zinc-600">No assigned games yet — join a class above.</p>
        )}
        {assignments.map((a) => (
          <Link
            key={a.assignment_id}
            href={`/play/${a.campaign_id}`}
            className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-3 text-left hover:border-amber-500/50"
          >
            <span className="text-zinc-100">{a.title}</span>
            <span className="text-xs text-zinc-500">{a.class_name} →</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
