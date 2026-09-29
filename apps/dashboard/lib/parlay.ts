// Port de apps/api/tennis_quant/parlay.py: o site estático calcula o bilhete no browser.
// Manter as duas versões alinhadas; parlay.test.mjs espelha tests/test_daily_and_parlay.py.

export type Leg = {fixture_id?: string; decimal_odds: number; bookmaker?: string; source?: string; observed_at?: string; start_at?: string};
export type Ticket = {kind: string; line_count: number; lines: {indices: number[]; decimal_odds: number; stake: number}[]; total_stake: number; max_gross_return: number; max_net_profit: number; same_bookmaker: boolean; provider_prices: boolean; status: string; note: string};

const SIX_HOURS = 6 * 3600 * 1000;
const HAS_TIMEZONE = /(Z|[+-]\d{2}:?\d{2})$/i;
const round = (value: number, digits: number) => Number(value.toFixed(digits));

function combinations(n: number, size: number): number[][] {
  const out: number[][] = [];
  const walk = (start: number, picked: number[]) => {
    if (picked.length === size) { out.push(picked); return; }
    for (let i = start; i < n; i++) walk(i + 1, [...picked, i]);
  };
  walk(0, []);
  return out;
}

function instant(value?: string): number | null {
  return value && HAS_TIMEZONE.test(value) && Number.isFinite(Date.parse(value)) ? Date.parse(value) : null;
}

export function calculateTicket(legs: Leg[], kind: string, totalStake = 10, systemSize: number | null = null): Ticket {
  if (legs.length < 1 || legs.length > 8) throw new Error("O bilhete aceita entre 1 e 8 seleções");
  if (!(totalStake > 0 && totalStake <= 100_000)) throw new Error("Montante inválido");
  if (legs.some(leg => !(leg.decimal_odds > 1 && leg.decimal_odds <= 1000))) throw new Error("Odds decimais inválidas");
  const fixtures = legs.filter(leg => leg.fixture_id).map(leg => leg.fixture_id);
  if (new Set(fixtures).size !== fixtures.length) throw new Error("Não é possível combinar seleções do mesmo jogo sem preço conjunto da casa");
  const n = legs.length;
  let sizes: number[];
  if (kind === "single") {
    if (n !== 1) throw new Error("Aposta simples exige uma seleção");
    sizes = [1];
  } else if (kind === "accumulator") {
    if (n < 2) throw new Error("Combinada exige duas ou mais seleções");
    sizes = [n];
  } else if (kind === "system") {
    if (systemSize == null || systemSize < 2 || systemSize > n) throw new Error("Escolhe um sistema k/N com 2 ≤ k ≤ N");
    sizes = [systemSize];
  } else if (kind === "round_robin") {
    if (n < 3) throw new Error("Round robin exige pelo menos três seleções");
    sizes = Array.from({length: n - 1}, (_, i) => i + 2);
  } else throw new Error("Tipo de bilhete desconhecido");
  const combos = sizes.flatMap(size => combinations(n, size));
  const stakeLine = totalStake / combos.length;
  const lines = combos.map(indices => ({indices, decimal_odds: round(indices.reduce((odds, i) => odds * legs[i].decimal_odds, 1), 4), stake: round(stakeLine, 4)}));
  const gross = lines.reduce((sum, line) => sum + stakeLine * line.decimal_odds, 0);
  // Odds manuais, mistura de casas e preços de fonte têm garantias de execução diferentes:
  // o bilhete nunca é apresentado como executável.
  const books = new Set(legs.map(leg => leg.bookmaker ?? null));
  const sameBook = books.size === 1 && [...books][0] !== null && [...books][0] !== "";
  const now = Date.now();
  const providerPrices = legs.every(leg => {
    const observed = instant(leg.observed_at);
    const start = instant(leg.start_at);
    return leg.source === "provider" && observed !== null && start !== null
      && now - observed >= 0 && now - observed <= SIX_HOURS && observed < start && start > now;
  });
  return {kind, line_count: lines.length, lines, total_stake: totalStake,
    max_gross_return: round(gross, 2), max_net_profit: round(gross - totalStake, 2),
    same_bookmaker: sameBook, provider_prices: providerPrices, status: "indicative_quote_not_accepted",
    note: sameBook && providerPrices
      ? "Preço teórico. A casa pode não aceitar a combinada ou aplicar regras e preços próprios."
      : "Cenário matemático: há odds manuais ou seleções sem uma casa comum verificável."};
}
