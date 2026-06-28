// Public surface of @syllabusslayer/shared.
// NOTE: supabaseClient is intentionally NOT re-exported here — it instantiates a
// client at import time, so import it explicitly via "@syllabusslayer/shared/supabaseClient".
export * from "./gameSchema";
export * from "./api";
