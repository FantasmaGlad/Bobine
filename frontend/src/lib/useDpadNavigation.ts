"use client";

import { useEffect } from "react";
import { pickEntryPoint, pickNeighbor, type Direction } from "@/lib/spatialNav";

/**
 * Navigation au D-pad (télécommande de TV, clavier, manette) dans TOUTES les interfaces
 * d'administration : les flèches déplacent le focus vers le bouton, le lien ou la carte voisin(e) dans la
 * direction demandée, Entrée ou Espace active l'élément. Avant, seuls /cinema, /grid, /kiosk et /radio
 * réagissaient à la télécommande (via useKioskRemote) ; le tableau de bord, la bibliothèque, le
 * planning, les réglages, le coach… restaient muets, ou le focus natif du WebView sautait de façon
 * imprévisible.
 *
 * Règles de cohabitation :
 *  - les écrans qui gèrent déjà la télécommande (useKioskRemote) n'activent pas ce hook ;
 *  - une touche déjà traitée par un composant (`defaultPrevented` : listes déroulantes, poignées de
 *    glisser-déposer, feuilles) est laissée tranquille ;
 *  - les champs de saisie et les listes natives gardent leurs flèches ; un curseur (range) garde
 *    gauche/droite pour régler la valeur et laisse haut/bas pour en sortir ;
 *  - quand une fenêtre modale ou un tiroir est ouvert, la navigation reste À L'INTÉRIEUR.
 */

const NATIVE_FOCUSABLE =
  'a[href], button, input:not([type="hidden"]), select, textarea, summary, [tabindex]:not([tabindex="-1"]), [role="button"], [role="tab"], [role="option"], [role="menuitem"], [contenteditable="true"]';

/** Conteneurs qui doivent garder le focus prisonnier tant qu'ils sont ouverts. */
const MODAL_SELECTOR = '[role="dialog"], .modal-content, .detail-drawer, .telemetry-drawer, .sheet-panel';

export const DPAD_MODE_ATTRIBUTE = "data-input-mode";

function isTextEntry(el: HTMLElement): boolean {
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag !== "INPUT") return false;
  const type = (el as HTMLInputElement).type;
  return !["button", "submit", "reset", "checkbox", "radio", "range", "color", "file", "image"].includes(type);
}

function isVisible(el: HTMLElement): boolean {
  if (el.hasAttribute("disabled") || el.getAttribute("aria-hidden") === "true") return false;
  const rect = el.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2) return false;
  const style = getComputedStyle(el);
  return style.visibility !== "hidden" && style.display !== "none" && style.pointerEvents !== "none";
}

/** Racines cliquables SANS rôle ni tabindex (cartes en `div` avec onClick) : curseur « main » hérité du parent exclu. */
function pointerRoots(scope: ParentNode, nativeFocusables: Set<HTMLElement>): HTMLElement[] {
  const found: HTMLElement[] = [];
  const all = scope.querySelectorAll<HTMLElement>("div, li, span, article, section, label, img, tr");
  for (const el of all) {
    if (nativeFocusables.has(el)) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width < 24 || rect.height < 16) continue;
    // Hors de l'écran élargi : inutile de le mesurer plus avant.
    if (rect.bottom < -window.innerHeight || rect.top > window.innerHeight * 2) continue;
    if (getComputedStyle(el).cursor !== "pointer") continue;
    const parent = el.parentElement;
    if (parent && getComputedStyle(parent).cursor === "pointer") continue;
    // Une carte qui contient déjà des éléments focalisables natifs laisse ceux-ci porter la navigation.
    if (el.querySelector(NATIVE_FOCUSABLE)) continue;
    found.push(el);
  }
  return found;
}

function collectCandidates(): HTMLElement[] {
  const modals = Array.from(document.querySelectorAll<HTMLElement>(MODAL_SELECTOR)).filter(isVisible);
  const scope: ParentNode = modals.length > 0 ? modals[modals.length - 1] : document;
  const native = Array.from(scope.querySelectorAll<HTMLElement>(NATIVE_FOCUSABLE)).filter(isVisible);
  const nativeSet = new Set(native);
  const pointer = pointerRoots(scope, nativeSet).filter(isVisible);
  return [...native, ...pointer];
}

function focusElement(el: HTMLElement) {
  // Un élément cliquable sans tabindex ne peut pas recevoir le focus : on le rend focalisable au besoin.
  if (!el.matches(NATIVE_FOCUSABLE)) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
  el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
}

const DIRECTIONS: Record<string, Direction> = {
  ArrowLeft: "left",
  ArrowRight: "right",
  ArrowUp: "up",
  ArrowDown: "down",
};

export function useDpadNavigation(enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const root = document.documentElement;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      const direction = DIRECTIONS[e.key];
      const target = e.target as HTMLElement | null;

      if (direction) {
        if (target && isTextEntry(target)) return;
        const isRange = target instanceof HTMLInputElement && target.type === "range";
        if (isRange && (direction === "left" || direction === "right")) return;

        const candidates = collectCandidates();
        if (candidates.length === 0) return;
        root.setAttribute(DPAD_MODE_ATTRIBUTE, "remote");

        const active = document.activeElement as HTMLElement | null;
        const current = active && active !== document.body ? candidates.find((c) => c === active || c.contains(active)) : undefined;
        if (!current) {
          // Rien n'est sélectionné : on entre par le coin haut-gauche de ce qui est visible à l'écran.
          const onScreen = candidates.filter((c) => {
            const r = c.getBoundingClientRect();
            return r.bottom > 0 && r.top < window.innerHeight && r.right > 0 && r.left < window.innerWidth;
          });
          const pool = onScreen.length > 0 ? onScreen : candidates;
          const entry = pickEntryPoint(pool.map((c) => c.getBoundingClientRect()));
          if (entry >= 0) {
            e.preventDefault();
            focusElement(pool[entry]);
          }
          return;
        }
        const next = pickNeighbor(
          current.getBoundingClientRect(),
          candidates.map((c) => c.getBoundingClientRect()),
          direction,
        );
        if (next >= 0) {
          e.preventDefault();
          focusElement(candidates[next]);
        }
        // Aucun voisin : on laisse le navigateur défiler la page (haut/bas en bout de liste).
        return;
      }

      if (e.key === "Enter" || e.key === " " || e.key === "Select" || e.key === "Ok") {
        if (!target || target === document.body || isTextEntry(target)) return;
        // Les éléments natifs (bouton, lien, case) réagissent déjà à Entrée/Espace.
        const native = ["BUTTON", "A", "INPUT", "SELECT", "SUMMARY", "TEXTAREA"].includes(target.tagName);
        if (native) return;
        if (e.key === " " && target.getAttribute("role") !== "button" && !target.hasAttribute("tabindex")) return;
        e.preventDefault();
        target.click();
      }
    };

    // Dès que la souris ou le doigt reprennent la main, on retire le halo de télécommande.
    const onPointer = () => root.removeAttribute(DPAD_MODE_ATTRIBUTE);

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointer, true);
    window.addEventListener("touchstart", onPointer, true);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onPointer, true);
      window.removeEventListener("touchstart", onPointer, true);
      root.removeAttribute(DPAD_MODE_ATTRIBUTE);
    };
  }, [enabled]);
}
