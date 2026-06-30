"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { type ClassOut, teacher } from "@/lib/api";

export default function ClassesPage() {
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () =>
    teacher
      .listClasses()
      .then(setClasses)
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await teacher.createClass(name.trim());
      setName("");
      load();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-10 text-zinc-100">
      <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-300">
        ← Home
      </Link>
      <h1 className="mt-2 text-2xl font-bold">My classes</h1>

      <form onSubmit={create} className="mt-5 flex gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New class name…"
          className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-zinc-100"
        />
        <button className="rounded-lg bg-emerald-500 px-5 py-2 font-semibold text-zinc-950 hover:bg-emerald-400">
          Create
        </button>
      </form>
      {err && <p className="mt-3 text-sm text-rose-400">{err}</p>}

      <div className="mt-6 flex flex-col gap-2">
        {loading && <p className="text-zinc-500">Loading…</p>}
        {!loading && classes.length === 0 && (
          <p className="text-zinc-500">No classes yet — create one above.</p>
        )}
        {classes.map((c) => (
          <Link
            key={c.id}
            href={`/classes/${c.id}`}
            className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900/60 px-5 py-4 hover:border-emerald-500/50"
          >
            <span className="font-medium">{c.name}</span>
            <span className="text-sm text-zinc-400">
              code <span className="font-mono text-emerald-300">{c.join_code}</span> ·{" "}
              {c.student_count} students
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
