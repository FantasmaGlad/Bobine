import type { NextConfig } from "next";

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
