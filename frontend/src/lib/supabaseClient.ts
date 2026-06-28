/**
 * Supabase browser client (auth + storage).
 * Only the public anon key is exposed here (NEXT_PUBLIC_*) — never the service key.
 * Import this from Client Components.
 */
import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

if (!url || !anonKey) {
  // Non-fatal in dev so the app still boots before Supabase is configured.
  console.warn(
    "[supabase] NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY not set — auth disabled.",
  );
}

export const supabase = createClient(url, anonKey);
