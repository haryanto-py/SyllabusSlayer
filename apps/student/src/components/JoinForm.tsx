"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

// Dev entry point: type a campaign id to start a run. Join-by-class-code arrives in M3.
export default function JoinForm() {
  const router = useRouter();
  const [id, setId] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (id.trim()) router.push(`/play/${id.trim()}`);
      }}
      className="mt-8 flex w-full max-w-sm items-center gap-2"
    >
      <input
        value={id}
        onChange={(e) => setId(e.target.value)}
        placeholder="campaign id"
        className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900/70 px-4 py-3 text-center font-mono tracking-widest text-zinc-300 placeholder:text-zinc-600"
      />
      <button
        type="submit"
        className="rounded-lg bg-amber-500/80 px-5 py-3 font-semibold text-zinc-950 hover:bg-amber-400"
      >
        Play
      </button>
    </form>
  );
}
