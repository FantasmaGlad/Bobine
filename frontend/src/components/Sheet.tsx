"use client";

import React, { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import Icon from "@/components/Icon";

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  /** Sous le titre, collé en haut pendant le défilement (champ de recherche, onglets). */
  header?: React.ReactNode;
  /** Barre d'actions collée en bas. */
  footer?: React.ReactNode;
  children: React.ReactNode;
  closeLabel?: string;
  /** Feuille haute (88 % de l'écran) plutôt qu'ajustée au contenu. */
  tall?: boolean;
}

/**
 * Feuille basse sur téléphone, fenêtre centrée au-delà de 700 px.
 * Verrouille le défilement de la page, se ferme avec Échap ou en touchant le voile.
 */
export default function Sheet({ open, onClose, title, header, footer, children, closeLabel = "Fermer", tall = false }: SheetProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const titleId = useId();
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); closeRef.current(); }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const controls = Array.from(panel.querySelectorAll<HTMLElement>('a[href],button,input,select,textarea,[tabindex]'))
        .filter((el) => !el.matches(':disabled,[tabindex="-1"],[hidden]') && el.getClientRects().length > 0);
      const first = controls[0];
      const last = controls.at(-1);
      if (!first) { event.preventDefault(); panel.focus(); }
      else if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKey);
    panelRef.current?.focus();
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="sheet-overlay" onClick={onClose}>
      <div
        ref={panelRef}
        className={`sheet-panel glass-floating${tall ? " sheet-panel--tall" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-label={title ? undefined : closeLabel}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sheet-handle" aria-hidden="true" />
        <div className="sheet-head">
          {title ? <h3 id={titleId} className="sheet-title">{title}</h3> : <span />}
          <button type="button" className="sheet-close olc-press" onClick={onClose} aria-label={closeLabel}>
            <Icon name="close" size={20} />
          </button>
        </div>
        {header ? <div className="sheet-sticky">{header}</div> : null}
        <div className="sheet-body">{children}</div>
        {footer ? <div className="sheet-footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
