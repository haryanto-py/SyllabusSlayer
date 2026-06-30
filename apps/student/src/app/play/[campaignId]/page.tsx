"use client";

import { useParams } from "next/navigation";

import Combat from "@/components/Combat";

export default function PlayPage() {
  const params = useParams();
  const campaignId = (params?.campaignId as string) ?? "";
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-zinc-950 to-zinc-900 text-zinc-100">
      <Combat campaignId={campaignId} />
    </div>
  );
}
