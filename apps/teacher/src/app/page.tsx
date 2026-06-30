import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-zinc-950 px-6 py-20 text-zinc-100">
      <main className="flex w-full max-w-2xl flex-col items-center text-center">
        <span className="mb-6 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-medium tracking-wide text-emerald-300">
          🧑‍🏫 Teacher
        </span>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          SyllabusSlayer <span className="text-emerald-400">Teacher</span>
        </h1>
        <p className="mt-5 max-w-lg text-lg leading-8 text-zinc-400">
          Review AI-generated questions, assign campaigns to a class, and monitor mastery.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/classes"
            className="rounded-lg bg-emerald-500 px-6 py-3 font-semibold text-zinc-950 hover:bg-emerald-400"
          >
            My classes
          </Link>
          <Link
            href="/campaigns"
            className="rounded-lg border border-zinc-700 px-6 py-3 font-semibold text-zinc-200 hover:bg-zinc-800"
          >
            Campaigns
          </Link>
        </div>
        <p className="mt-3 text-xs text-zinc-600">
          Dev mode (no login yet) — Supabase auth arrives in M3-T6.
        </p>
      </main>
    </div>
  );
}
