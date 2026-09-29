import MatchDetail from "./MatchDetail";
import { STATIC } from "../../../lib/api";

// O arquivo só existe com a API Python. O export estático exige pelo menos uma rota, por isso
// só nesse modo há uma página-marcador («Jogo indisponível», sem links). Em local não pode existir:
// o Next tentaria guardar em cache cada jogo e o ":" dos IDs não é válido em ficheiros no Windows.
export const generateStaticParams = STATIC ? () => [{ id: "indisponivel" }] : undefined;

export default function GameDetail() { return <MatchDetail />; }
