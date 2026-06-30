"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { type CampaignDetail, type ReviewQuestion, teacher } from "@/lib/api";

export default function ReviewPage() {
  const params = useParams();
  const campaignId = (params?.campaignId as string) ?? "";
  const [data, setData] = useState<CampaignDetail | null>(null);
  const [status, setStatus] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!campaignId) return;
    teacher
      .getCampaign(campaignId)
      .then((d) => {
        setData(d);
        setStatus(d.status);
      })
      .catch((e) => setErr(String(e)));
  }, [campaignId]);

  if (!data) return <div className="p-10 text-zinc-400">Loading…</div>;

  const publish = async () => {
    try {
      const r = await teacher.publish(campaignId);
      setStatus(r.status);
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-10 text-zinc-100">
      <Link href="/campaigns" className="text-sm text-zinc-500 hover:text-zinc-300">
        ← Campaigns
      </Link>
      <div className="mt-2 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{data.title}</h1>
        <button
          onClick={publish}
          className="shrink-0 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-zinc-950 hover:bg-emerald-400"
        >
          {status === "published" ? "Published ✓ (republish)" : "Publish"}
        </button>
      </div>
      {err && <p className="mt-2 text-sm text-rose-400">{err}</p>}

      {data.game.acts.map((act) => (
        <section key={act.actId} className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-emerald-400">
            {act.title}
          </h2>
          {act.encounters.map((enc) => (
            <div key={enc.encounterId} className="mt-2">
              <p className="text-xs text-zinc-500">
                {enc.kind} · {enc.title}
              </p>
              {enc.questions.map((q) => (
                <QuestionEditor key={q.questionId} campaignId={campaignId} q={q} />
              ))}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

function QuestionEditor({ campaignId, q }: { campaignId: string; q: ReviewQuestion }) {
  const [prompt, setPrompt] = useState(q.prompt);
  const [explanation, setExplanation] = useState(q.explanation);
  const [options, setOptions] = useState(q.options ?? []);
  const [correct, setCorrect] = useState((q.correctOptionIds ?? [])[0] ?? "");
  const [correctBool, setCorrectBool] = useState<boolean | null>(q.correctBoolean ?? null);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    setErr(null);
    const isChoice = q.questionType === "multiple_choice" || q.questionType === "multi_select";
    const updated: ReviewQuestion = {
      ...q,
      prompt,
      explanation,
      options: isChoice ? options : q.options,
      correctOptionIds:
        q.questionType === "multiple_choice" ? (correct ? [correct] : []) : q.correctOptionIds,
      correctBoolean: q.questionType === "true_false" ? correctBool : q.correctBoolean,
    };
    try {
      await teacher.editQuestion(campaignId, q.questionId, updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="mt-2 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <div className="mb-1 text-[10px] uppercase text-zinc-500">
        {q.questionType} · {q.bloomLevel} · {q.difficulty}
      </div>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={2}
        className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
      />
      {q.questionType === "multiple_choice" && (
        <div className="mt-2 flex flex-col gap-1">
          {options.map((o, i) => (
            <label key={o.optionId} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={`c-${q.questionId}`}
                checked={correct === o.optionId}
                onChange={() => setCorrect(o.optionId)}
              />
              <input
                value={o.text}
                onChange={(e) =>
                  setOptions(options.map((x, xi) => (xi === i ? { ...x, text: e.target.value } : x)))
                }
                className="flex-1 rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
              />
            </label>
          ))}
        </div>
      )}
      {q.questionType === "true_false" && (
        <div className="mt-2 flex gap-4 text-sm">
          <label className="flex items-center gap-1">
            <input
              type="radio"
              name={`tf-${q.questionId}`}
              checked={correctBool === true}
              onChange={() => setCorrectBool(true)}
            />{" "}
            True
          </label>
          <label className="flex items-center gap-1">
            <input
              type="radio"
              name={`tf-${q.questionId}`}
              checked={correctBool === false}
              onChange={() => setCorrectBool(false)}
            />{" "}
            False
          </label>
        </div>
      )}
      <textarea
        value={explanation}
        onChange={(e) => setExplanation(e.target.value)}
        rows={2}
        placeholder="Explanation"
        className="mt-2 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-400"
      />
      <div className="mt-2 flex items-center gap-3">
        <button
          onClick={save}
          className="rounded bg-zinc-100 px-4 py-1.5 text-sm font-semibold text-zinc-900 hover:bg-white"
        >
          Save
        </button>
        {saved && <span className="text-xs text-emerald-400">saved ✓</span>}
        {err && <span className="text-xs text-rose-400">{err}</span>}
      </div>
    </div>
  );
}
