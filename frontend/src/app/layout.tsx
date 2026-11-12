import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import localFont from "next/font/local";
import "./globals.css";
import "./themes.css";
import "./responsive.css";
import ClientLayout from "@/components/ClientLayout";
import { translate, UI_LANGUAGE } from "@/lib/i18n";
import { AppSettingsProvider } from "@/lib/AppSettingsContext";
import { InlineScript } from "@/components/InlineScript";
import { UploadManagerProvider } from "@/lib/UploadManager";
import { DEFAULT_MODE, DEFAULT_THEME, LEGACY_THEMES, paletteOf, THEME_IDS } from "@/lib/themePalettes";

// Applique le thème/la langue mis en cache (localStorage) avant même
// l'hydratation React, pour éviter un flash du mauvais thème au premier
// affichage — script bloquant volontaire
// (pas de défer/async), s'exécute donc avant tout rendu visible. Le contenu
// est statique (jamais de données utilisateur injectées ici), sans risque XSS.
// Les noms, la table des anciens thèmes et le défaut viennent de lib/themePalettes.ts (aucune liste en double) ; le mode
// « auto » suit prefers-color-scheme, comme le fait AppSettingsContext ensuite.
const THEME_INIT_SCRIPT = `(function(){try{var d=document.documentElement,ids=${JSON.stringify(THEME_IDS)},legacy=${JSON.stringify(LEGACY_THEMES)},t=localStorage.getItem('olc-theme'),m=localStorage.getItem('olc-theme-mode'),l=t&&legacy[t];if(l&&(ids.indexOf(t)<0||(m!=='light'&&m!=='dark'&&m!=='auto'))){t=l.theme;m=(m==='light'||m==='dark')?m:l.mode;}if(ids.indexOf(t)<0)t=${JSON.stringify(DEFAULT_THEME)};if(m!=='light'&&m!=='dark'&&m!=='auto')m=${JSON.stringify(DEFAULT_MODE)};if(m==='auto')m=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';d.setAttribute('data-theme',t);d.setAttribute('data-mode',m);}catch(e){}})();`;

// Polices embarquées dans l'export : Bobine tourne sans Internet, aucune ressource n'est chargée d'un tiers.
const materialSymbols = localFont({
  src: "../../node_modules/material-symbols/material-symbols-outlined.woff2",
  variable: "--font-material-symbols",
  weight: "100 700",
  display: "block",
  preload: false,
});

export const metadata: Metadata = {
  title: "Bobine - Administration",
  description: translate("app.metaDescription"),
  manifest: "/manifest.json",
};

// ces meta forcent le
// mode standalone (sans barre d'adresse) quand la page est ajoutée à l'écran
// d'accueil (Android/iOS). Un vrai plein écran navigateur (Fullscreen API)
// exige un geste utilisateur — voir le hook useAutoFullscreen déclenché au
// premier tap, dans ClientLayout.
export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover" as const,
  // Couleur du navigateur : le fond du thème par défaut dans chaque mode (lib/themePalettes.ts), avant tout réglage.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: paletteOf(DEFAULT_THEME, "light").bg },
    { media: "(prefers-color-scheme: dark)", color: paletteOf(DEFAULT_THEME, "dark").bg },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang={UI_LANGUAGE}
      data-theme={DEFAULT_THEME}
      data-mode="light"
      className={`${GeistSans.variable} ${GeistMono.variable} ${materialSymbols.variable}`}
      suppressHydrationWarning
    >
      <head>
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        {/* Icône requise pour que la PWA soit réellement installable : avec `icons: []`
            dans le manifest, Chrome Android ne créait qu'un simple raccourci
            qui rouvrait le navigateur classique — le mode
            fullscreen/standalone du manifest était ignoré. */}
        <link rel="apple-touch-icon" href="/icon-192.png" />
        <InlineScript html={THEME_INIT_SCRIPT} />
      </head>
      <body>
        <AppSettingsProvider>
          <UploadManagerProvider>
            <ClientLayout>{children}</ClientLayout>
          </UploadManagerProvider>
        </AppSettingsProvider>
      </body>
    </html>
  );
}

