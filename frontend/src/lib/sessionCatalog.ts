/**
 * Dernière donnée connue d'une liste (catalogue de cours, cours audio) gardée en mémoire pour la durée de la session :
 * un écran qu'on rouvre s'affiche aussitôt avec ce qu'il montrait, puis la lecture réseau le remplace. Rien n'est
 * persisté (ni stockage local, ni disque) : un rechargement de la page repart de zéro.
 */
const catalog = new Map<string, unknown>();

export function rememberCatalog<T>(key: string, value: T[]): void {
  catalog.set(key, value);
}

export function recallCatalog<T>(key: string): T[] | undefined {
  const value = catalog.get(key);
  return Array.isArray(value) ? (value as T[]) : undefined;
}
