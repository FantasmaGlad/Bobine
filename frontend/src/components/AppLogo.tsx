"use client";

import React, { useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";

interface AppLogoProps {
  size?: number;
  className?: string;
}

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

/**
 * Logo de l'application : celui personnalisé uploadé depuis Paramètres
 * (réf. mission "customiser le logo") si présent, sinon le logo Bobine par
 * défaut (/public/logo.png). `size` est la HAUTEUR affichée (px) ; le
 * bandeau par défaut fait ~2,34× cette hauteur en largeur. Si `size` est
 * omis, aucune hauteur inline n'est posée : c'est alors la classe CSS
 * (`className`) qui pilote la taille — utile pour un logo responsive (ex.
 * écran radio « hors diffusion », réf. .radio-brand-logo).
 */
export default function AppLogo({ size, className }: AppLogoProps) {
  const { hasCustomLogo, logoVersion } = useAppSettings();
  const [customFailed, setCustomFailed] = useState(false);
  // Un nouvel upload peut remplacer un logo custom précédemment en échec de
  // chargement (fichier corrompu) : retenter à chaque changement de version
  // plutôt que de rester bloqué sur le fallback par défaut.
  useEffect(() => setCustomFailed(false), [logoVersion]);
  const useCustom = hasCustomLogo && !customFailed;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={useCustom ? `${getApiUrl("/branding/logo.png")}?v=${logoVersion}` : "/logo.png"}
      alt="Bobine"
      // Le logo par défaut est un pictogramme monochrome recoloré via
      // --logo-filter selon le thème (cf. globals.css) ; un logo custom en
      // couleur ne doit PAS hériter de ce filtre, d'où le modificateur.
      className={`app-logo${useCustom ? " app-logo--custom" : ""}${className ? ` ${className}` : ""}`}
      // `width: "auto"` uniquement quand `size` est fourni (réf. revue de
      // code) : posé inconditionnellement, il gagnerait TOUJOURS sur un
      // `width` fixé par la classe CSS (ex. .kiosk-waiting-stage-logo,
      // width:100%) puisqu'un style inline prime sur une règle de classe —
      // cassant le contrat documenté ci-dessus ("si size est omis, la classe
      // CSS pilote la taille") et laissant un logo à un ratio différent du
      // défaut déborder de sa cellule plutôt que se contenir dedans.
      style={size ? { height: size, width: "auto", display: "block" } : { display: "block" }}
      onError={() => setCustomFailed(true)}
    />
  );
}
