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
  const { hasCustomLogo, activeLogo, logoVersion } = useAppSettings();
  const [customFailed, setCustomFailed] = useState(false);
  // Un nouvel upload peut remplacer un logo custom précédemment en échec de
  // chargement (fichier corrompu) : retenter à chaque changement de version
  // plutôt que de rester bloqué sur le fallback par défaut.
  useEffect(() => setCustomFailed(false), [logoVersion]);
  const useCustom = activeLogo === "custom" && hasCustomLogo && !customFailed;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={useCustom ? `${getApiUrl("/branding/logo.png")}?v=${logoVersion}` : "/logo.png"}
      alt="Bobine"
      // Le logo par défaut est un pictogramme monochrome recoloré via
      // --logo-filter selon le thème (cf. globals.css) ; un logo custom en
      // couleur ne doit PAS hériter de ce filtre, d'où le modificateur.
      className={`app-logo${useCustom ? " app-logo--custom" : ""}${className ? ` ${className}` : ""}`}
      style={
        size
          ? { maxHeight: size, maxWidth: "100%", width: "auto", height: "auto", display: "block", objectFit: "contain" }
          : { maxWidth: "100%", maxHeight: "100%", display: "block", objectFit: "contain" }
      }
      onError={() => setCustomFailed(true)}
    />
  );
}
