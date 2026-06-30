import { SCHEMA_VERSION } from "@syllabusslayer/shared";

import JoinForm from "@/components/JoinForm";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-gradient-to-b from-zinc-950 to-zinc-900 px-6 py-20 text-zinc-100">
      <main className="flex w-full max-w-xl flex-col items-center text-center">
        <span className="mb-6 rounded-full border border-violet-500/40 bg-violet-500/10 px-3 py-1 text-xs font-medium tracking-wide text-violet-300">
          🎮 Student
        </span>

        <h1 className="bg-gradient-to-r from-amber-200 via-rose-300 to-violet-300 bg-clip-text text-5xl font-extrabold tracking-tight text-transparent sm:text-6xl">
          SyllabusSlayer
        </h1>

        <p className="mt-5 max-w-md text-lg leading-8 text-zinc-400">
          Enter your class code to start your run. Defeat topic bosses, chain streaks for
          bonus damage, and conquer the course.
        </p>

        <JoinForm />
        <p className="mt-3 text-xs text-zinc-600">
          Enter a campaign id to start a run. (Join-by-class-code arrives in M3.)
        </p>

        <p className="mt-12 text-xs text-zinc-700">schema v{SCHEMA_VERSION} · student app</p>
      </main>
    </div>
  );
}
