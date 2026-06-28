export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-gradient-to-b from-zinc-950 to-zinc-900 px-6 py-20 text-zinc-100">
      <main className="flex w-full max-w-3xl flex-col items-center text-center">
        <span className="mb-6 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-medium tracking-wide text-amber-300">
          ⚔️ M0 scaffold
        </span>

        <h1 className="bg-gradient-to-r from-amber-200 via-rose-300 to-violet-300 bg-clip-text text-5xl font-extrabold tracking-tight text-transparent sm:text-6xl">
          SyllabusSlayer
        </h1>

        <p className="mt-5 max-w-xl text-lg leading-8 text-zinc-400">
          Upload a syllabus, get a <span className="text-zinc-200">roguelike</span>. An AI
          pipeline turns a teacher&apos;s own materials into a quiz-RPG — battle topic
          bosses, chain streaks for bonus damage, and conquer the course.
        </p>

        <div className="mt-10 grid w-full gap-4 sm:grid-cols-2">
          <RoleCard
            title="I'm a teacher"
            desc="Upload resources, review AI-generated questions, assign, and monitor mastery."
            href="/teacher"
          />
          <RoleCard
            title="I'm a student"
            desc="Join with a class code and fight your way through the campaign."
            href="/student"
          />
        </div>

        <p className="mt-12 text-sm text-zinc-600">
          FastAPI · Next.js · OpenAI · Supabase — see{" "}
          <code className="text-zinc-400">docs/BUILD-SPEC.md</code>
        </p>
      </main>
    </div>
  );
}

function RoleCard({ title, desc, href }: { title: string; desc: string; href: string }) {
  return (
    <a
      href={href}
      className="group rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 text-left transition-colors hover:border-amber-500/50 hover:bg-zinc-900"
    >
      <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-zinc-400">{desc}</p>
      <span className="mt-4 inline-block text-sm font-medium text-amber-400 opacity-0 transition-opacity group-hover:opacity-100">
        Coming in M3 →
      </span>
    </a>
  );
}
