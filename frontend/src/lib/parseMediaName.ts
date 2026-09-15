// Détecte le schéma "<Catégorie> <Édition>" dans un nom de fichier/dossier
// importé (ex. "Rpm 101.mp4" -> catégorie "Rpm", édition "101") — utilisé au
// pré-remplissage des champs d'import vidéo (Bibliothèque) et audio (Coach).
//
// Réf. bug "chiffre random affiché sur la tablette à la place de l'édition" :
// l'ancienne heuristique (regex `(?:release|rel|r|#|v)\s*(\d+)`) cherchait
// une simple lettre "r" suivie d'un chiffre n'importe où dans le nom, ce qui
// pouvait accrocher un numéro de piste, une date ou une résolution vidéo
// plutôt que l'édition réelle. Ici le chiffre retenu doit être collé à un mot
// ("Rpm 101", "Rpm_101", "Rpm-101"), et les nombres à 4 chiffres qui
// ressemblent à une année ou une résolution vidéo sont ignorés sauf si le mot
// qui les précède est une catégorie déjà connue.
const RESOLUTION_NUMBERS = new Set(["144", "240", "360", "480", "720", "1080", "1440", "2160", "4320"]);

export interface ParsedMediaName {
  title: string;
  program: string;
  release: string;
}

export function parseMediaName(rawName: string, knownPrograms: string[] = []): ParsedMediaName {
  const nameWithoutExt = rawName.replace(/\.[a-z0-9]{2,5}$/i, "");
  const cleaned = nameWithoutExt.replace(/[_.]+/g, " ").trim();

  const pattern = /([A-Za-zÀ-ÖØ-öø-ÿ]+)[\s-]+(\d{1,4})\b/g;
  let match: RegExpExecArray | null;
  let picked: { word: string; number: string } | null = null;
  while ((match = pattern.exec(cleaned)) !== null) {
    const [, word, number] = match;
    const isFourDigit = number.length === 4;
    const isYear = isFourDigit && Number(number) >= 1900 && Number(number) <= 2099;
    const isResolution = RESOLUTION_NUMBERS.has(number);
    const isKnownWord = knownPrograms.some((p) => p && p.toLowerCase() === word.toLowerCase());
    if ((isYear || isResolution) && !isKnownWord) continue;
    picked = { word, number };
    break;
  }

  if (picked) {
    const known = knownPrograms.find((p) => p && p.toLowerCase() === picked!.word.toLowerCase());
    const program = known ?? picked.word.charAt(0).toUpperCase() + picked.word.slice(1).toLowerCase();
    return { title: `${program} ${picked.number}`, program, release: picked.number };
  }

  const knownInName = knownPrograms.find((p) => p && cleaned.toLowerCase().includes(p.toLowerCase())) ?? "";
  return { title: cleaned, program: knownInName, release: "" };
}
