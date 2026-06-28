import { SCHEMA_VERSION } from "@syllabusslayer/shared";

const STEPS = ["Upload", "Review & edit", "Assign", "Dashboard"];

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
          Turn your syllabus into a roguelike. Upload resources, review AI-generated
          questions, assign to a class, and monitor mastery.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3 text-sm">
          {STEPS.map((step, i) => (
            <span
              key={step}
              className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-2 text-zinc-300"
            >
              {i + 1}. {step}
            </span>
          ))}
        </div>

        <button
          type="button"
          disabled
          className="mt-8 rounded-lg bg-emerald-500/80 px-6 py-3 font-semibold text-zinc-950"
        >
          Sign in
        </button>
        <p className="mt-3 text-xs text-zinc-600">Auth + workflow arrive in M3.</p>

        <p className="mt-12 text-xs text-zinc-700">schema v{SCHEMA_VERSION} · teacher app</p>
      </main>
    </div>
  );
}
