/**
 * Supabase browser client (auth + storage). Shared by both apps.
 * Only the public anon key is exposed (NEXT_PUBLIC_*) — never the service key.
 * Import explicitly: `import { supabase } from "@syllabusslayer/shared/supabaseClient";`
 */
import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

if (!url || !anonKey) {
  console.warn(
    "[supabase] NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY not set — auth disabled.",
  );
}

export const supabase = createClient(url, anonKey);
