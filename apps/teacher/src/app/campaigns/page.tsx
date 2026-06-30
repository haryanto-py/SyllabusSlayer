"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { type CampaignSummary, teacher } from "@/lib/api";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    teacher
      .listCampaigns()
      .then(setCampaigns)
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-10 text-zinc-100">
      <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-300">
        ← Home
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Campaigns</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Generated games. Open one to review questions before assigning. (Generate new ones via
        the API / <code>scripts/m1_demo.py</code> for now.)
      </p>

      {err && <p className="mt-3 text-sm text-rose-400">{err}</p>}
      <div className="mt-6 flex flex-col gap-2">
        {loading && <p className="text-zinc-500">Loading…</p>}
        {!loading && campaigns.length === 0 && (
          <p className="text-zinc-500">No campaigns yet.</p>
        )}
        {campaigns.map((c) => (
          <Link
            key={c.id}
            href={`/campaigns/${c.id}`}
            className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900/60 px-5 py-4 hover:border-emerald-500/50"
          >
            <span className="font-medium">{c.title}</span>
            <span
              className={`rounded px-2 py-0.5 text-xs ${
                c.status === "published"
                  ? "bg-emerald-500/20 text-emerald-300"
                  : "bg-zinc-700/50 text-zinc-300"
              }`}
            >
              {c.status}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
