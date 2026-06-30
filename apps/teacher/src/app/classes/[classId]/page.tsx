"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  type Analytics,
  type AssignmentOut,
  type CampaignSummary,
  type ClassDetail,
  teacher,
} from "@/lib/api";

export default function ClassDetailPage() {
  const params = useParams();
  const classId = (params?.classId as string) ?? "";
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [assignments, setAssignments] = useState<AssignmentOut[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [pick, setPick] = useState("");
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refreshAssignments = () =>
    teacher.listAssignments(classId).then(setAssignments).catch(() => {});

  useEffect(() => {
    if (!classId) return;
    teacher.classDetail(classId).then(setDetail).catch((e) => setErr(String(e)));
    refreshAssignments();
    teacher.listCampaigns().then(setCampaigns).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId]);

  const assign = async () => {
    if (!pick) return;
    try {
      await teacher.assign(classId, pick);
      setPick("");
      refreshAssignments();
    } catch (e) {
      setErr(String(e));
    }
  };

  if (!detail) return <div className="p-10 text-zinc-400">Loading…</div>;

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-6 py-10 text-zinc-100">
      <Link href="/classes" className="text-sm text-zinc-500 hover:text-zinc-300">
        ← Classes
      </Link>
      <h1 className="mt-2 text-2xl font-bold">{detail.name}</h1>
      <p className="mt-1 text-sm text-zinc-400">
        Join code: <span className="font-mono text-emerald-300">{detail.join_code}</span>
      </p>
      {err && <p className="mt-3 text-sm text-rose-400">{err}</p>}

      {/* Roster */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Roster ({detail.roster.length})
        </h2>
        <div className="mt-2 rounded-xl border border-zinc-800 bg-zinc-900/60">
          {detail.roster.length === 0 ? (
            <p className="px-4 py-3 text-sm text-zinc-500">No students yet — share the join code.</p>
          ) : (
            detail.roster.map((s) => (
              <div key={s.id} className="border-b border-zinc-800 px-4 py-2 text-sm last:border-0">
                {s.display_name} <span className="text-zinc-500">· {s.email}</span>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Assign */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Assign a campaign</h2>
        <div className="mt-2 flex gap-2">
          <select
            value={pick}
            onChange={(e) => setPick(e.target.value)}
            className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-zinc-100"
          >
            <option value="">— pick a campaign —</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} ({c.status})
              </option>
            ))}
          </select>
          <button
            onClick={assign}
            disabled={!pick}
            className="rounded-lg bg-emerald-500 px-5 py-2 font-semibold text-zinc-950 hover:bg-emerald-400 disabled:opacity-40"
          >
            Assign
          </button>
        </div>
        <div className="mt-3 flex flex-col gap-2">
          {assignments.map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2 text-sm"
            >
              <span>{a.campaign_title}</span>
              <button
                onClick={() => teacher.analytics(a.campaign_id, classId).then(setAnalytics).catch((e) => setErr(String(e)))}
                className="rounded border border-zinc-700 px-3 py-1 text-zinc-300 hover:bg-zinc-800"
              >
                Dashboard
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Analytics */}
      {analytics && <Dashboard data={analytics} />}
    </div>
  );
}

function pct(n: number) {
  return `${Math.round(n * 100)}%`;
}

function Dashboard({ data }: { data: Analytics }) {
  return (
    <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
      <h2 className="text-lg font-bold">Dashboard</h2>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Roster" value={data.summary.roster_size} />
        <Stat label="Started" value={data.summary.started} />
        <Stat label="Completed" value={data.summary.completed} />
        <Stat label="Avg accuracy" value={pct(data.summary.avg_accuracy)} />
      </div>

      <h3 className="mt-5 text-sm font-semibold uppercase tracking-wide text-zinc-500">Students</h3>
      <Table
        head={["Student", "Attempts", "Accuracy", "Best score", "Done"]}
        rows={data.students.map((s) => [
          s.name,
          String(s.attempts),
          pct(s.accuracy),
          String(s.best_score),
          s.completed ? "✓" : "—",
        ])}
      />

      <h3 className="mt-5 text-sm font-semibold uppercase tracking-wide text-zinc-500">
        Topic mastery
      </h3>
      <Table
        head={["Topic", "Attempts", "Accuracy"]}
        rows={data.topics.map((t) => [t.topic, String(t.attempts), pct(t.accuracy)])}
      />
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-center">
      <div className="text-xl font-bold text-emerald-300">{value}</div>
      <div className="text-xs text-zinc-500">{label}</div>
    </div>
  );
}

function Table({ head, rows }: { head: string[]; rows: string[][] }) {
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-zinc-800">
      <table className="w-full text-sm">
        <thead className="bg-zinc-900 text-zinc-400">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 text-left font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={head.length} className="px-3 py-3 text-zinc-500">
                No data yet.
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr key={i} className="border-t border-zinc-800">
                {r.map((c, j) => (
                  <td key={j} className="px-3 py-2 text-zinc-200">
                    {c}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
