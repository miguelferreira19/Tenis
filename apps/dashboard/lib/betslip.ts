export type SlipLeg = {
  id: string;
  fixture_id?: string;
  match: string;
  selection: string;
  decimal_odds: number;
  bookmaker?: string;
  observed_at?: string;
  start_at?: string;
  source: "provider" | "manual";
  alternatives?: {id: string; bookmaker: string; decimal_odds: number; observed_at: string}[];
};

const KEY = "tennis-quant-slip-v2";

export function readSlip(): SlipLeg[] {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(value) ? value.filter((x) => x && typeof x.id === "string" && typeof x.decimal_odds === "number").slice(0, 8) : [];
  } catch { return []; }
}

export function writeSlip(legs: SlipLeg[]) {
  localStorage.setItem(KEY, JSON.stringify(legs));
  window.dispatchEvent(new Event("tennis-slip-change"));
}
