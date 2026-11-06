import type { NextConfig } from "next";

// Un export statique par langue (scripts/build.mjs fixe NEXT_PUBLIC_BOBINE_LANG) : chaque écran n'embarque que le
// dictionnaire de sa langue. Le backend sert celui de la langue enregistrée.
const language = process.env.NEXT_PUBLIC_BOBINE_LANG === "en" ? "en" : "fr";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  turbopack: {
    resolveAlias: {
      "@bobine/dictionary": `./src/lib/i18n/${language}.ts`,
    },
  },
};

export default nextConfig;
