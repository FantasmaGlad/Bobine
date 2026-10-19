/**
 * Recherche tolérante, partagée par TOUS les champs de recherche et listes déroulantes — logique PURE,
 * sans DOM, pour rester testable (`frontend/tests/`).
 *
 * Règles : insensible à la casse ET aux accents (« ete » trouve « Été »), tous les mots saisis doivent se
 * retrouver (dans n'importe quel ordre), et le classement favorise le début du texte puis le début d'un
 * mot — ce qui donne l'autocomplétion attendue (« bass » propose « Bass Boost » avant « Sub bass »).
 */

/** Minuscules sans accents ni diacritiques, espaces réduits. */
export function normalizeText(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
}

/** Mots de la requête, normalisés, sans doublon ni mot vide. */
export function queryTokens(query: string): string[] {
  const unique = new Set(normalizeText(query).split(" ").filter(Boolean));
  return [...unique];
}

/** Vrai si tous les mots de la requête figurent dans le texte (requête vide = tout correspond). */
export function matchesQuery(text: string, query: string): boolean {
  const tokens = queryTokens(query);
  if (tokens.length === 0) return true;
  const haystack = normalizeText(text);
  return tokens.every((token) => haystack.includes(token));
}

/**
 * Score de pertinence (0 = ne correspond pas) : texte qui commence par la requête > début de mot >
 * simple inclusion ; l'ordre des mots saisis est un bonus. Plus le score est haut, mieux c'est.
 */
export function scoreMatch(text: string, query: string): number {
  const tokens = queryTokens(query);
  if (tokens.length === 0) return 1;
  const haystack = normalizeText(text);
  let score = 0;
  for (const token of tokens) {
    const at = haystack.indexOf(token);
    if (at < 0) return 0;
    if (at === 0) score += 6;
    else if (haystack[at - 1] === " " || /[-_/(]/.test(haystack[at - 1])) score += 4;
    else score += 1;
  }
  if (haystack.startsWith(normalizeText(query))) score += 4;
  return score;
}

/** Éléments correspondants, du plus pertinent au moins pertinent (ordre d'origine à score égal). */
export function rankByQuery<T>(items: readonly T[], query: string, getText: (item: T) => string): T[] {
  if (queryTokens(query).length === 0) return [...items];
  return items
    .map((item, index) => ({ item, index, score: scoreMatch(getText(item), query) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map((entry) => entry.item);
}

/**
 * Suggestions d'autocomplétion : textes UNIQUES (casse et accents ignorés) classés par pertinence, la
 * requête exacte elle-même étant écartée (inutile de proposer ce qui est déjà tapé).
 */
export function suggestFrom(candidates: readonly string[], query: string, limit = 6): string[] {
  const typed = normalizeText(query);
  if (!typed) return [];
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const candidate of candidates) {
    const key = normalizeText(candidate);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    unique.push(candidate);
  }
  return rankByQuery(unique, query, (text) => text)
    .filter((text) => normalizeText(text) !== typed)
    .slice(0, limit);
}

export interface TextSegment {
  text: string;
  match: boolean;
}

/**
 * Découpe un texte en segments « trouvé / non trouvé » pour surligner la recherche, en respectant le
 * texte d'ORIGINE (accents et casse conservés) alors que la comparaison est normalisée.
 */
export function highlightSegments(text: string, query: string): TextSegment[] {
  const tokens = queryTokens(query);
  if (tokens.length === 0 || !text) return [{ text, match: false }];
  // Normalisation caractère par caractère : conserve la correspondance d'indices avec l'original.
  let normalized = "";
  const origin: number[] = [];
  for (let i = 0; i < text.length; i++) {
    const piece = text[i].normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    for (let k = 0; k < piece.length; k++) origin.push(i);
    normalized += piece;
  }
  const marked = new Array<boolean>(text.length).fill(false);
  for (const token of tokens) {
    let from = 0;
    for (;;) {
      const at = normalized.indexOf(token, from);
      if (at < 0) break;
      for (let k = at; k < at + token.length; k++) marked[origin[k]] = true;
      from = at + token.length;
    }
  }
  const segments: TextSegment[] = [];
  for (let i = 0; i < text.length; i++) {
    const last = segments[segments.length - 1];
    if (last && last.match === marked[i]) last.text += text[i];
    else segments.push({ text: text[i], match: marked[i] });
  }
  return segments;
}
