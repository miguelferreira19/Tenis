export type Price = {fixture_id:string; player:string; match:string; probability:number; odds:number; start_at:string; observed_at:string; url:string; tour:string};
export type Limits = {bank:number; perBet:number; total:number; minimum:number; haircut:number; open:number};
export function makePlan(prices:Price[], limits:Limits, now:number) {
  const {bank,perBet,total,minimum,haircut,open} = limits;
  if (![bank,perBet,total,minimum,haircut,open,now].every(Number.isFinite) || bank<=0 || perBet<=0 || perBet>5 || total<=0 || total>10 || minimum<=0 || haircut<0 || haircut>25 || open<0 || open>bank) throw new Error("Revê os limites: banca positiva, 0–5% por aposta, 0–10% no total e valores finitos.");
  const cents = (value:number) => Math.floor((value+1e-9)*100)/100;
  let available = cents(Math.max(0,Math.min(bank*total/100-open,bank-open)));
  const used = new Set<string>();
  const rows = prices.map(price => {
    const valid = Number.isFinite(price.probability) && price.probability>0 && price.probability<1 && Number.isFinite(price.odds) && price.odds>1 && price.odds<=1000;
    const adjusted = valid ? Math.max(0,price.probability-haircut/100) : 0;
    const ev = valid ? adjusted*price.odds-1 : -1;
    const kelly = valid ? Math.max(0,ev/(price.odds-1)) : 0;
    const age = now-Date.parse(price.observed_at);
    const fresh = Number.isFinite(age) && age>=0 && age<=6*3600000;
    const upcoming = Date.parse(price.start_at)>now;
    return {...price,adjusted,ev,kelly,valid,fresh,upcoming};
  }).sort((a,b)=>b.ev-a.ev);
  return rows.map(row=> {
    let reason = !row.valid ? "Dados inválidos" : !row.upcoming ? "Jogo já iniciado / hora indisponível" : !row.fresh ? "Cotação expirada: confirmar novamente" : row.ev<=0 ? "Sem vantagem após margem de prudência" : used.has(row.fixture_id) ? "Outro lado do mesmo jogo já selecionado" : "";
    const proposed = cents(Math.min(bank*row.kelly/4,bank*perBet/100,available));
    if (!reason && proposed<minimum) reason = "Montante abaixo do mínimo ou limite total atingido";
    const simulated = reason ? 0 : proposed;
    if (simulated>0) {available=cents(available-simulated);used.add(row.fixture_id);}
    return {...row,simulated,real:0,reason:reason || "Simulação elegível; modelo ainda não aprovado"};
  });
}
