import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import compat from "eslint-plugin-compat";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Compatibilité navigateurs signale toute API Web
  // absente d'un des navigateurs de la politique de support (voir
  // `browserslist` dans package.json : Firefox ESR et courant, Chromium, Safari).
  compat.configs["flat/recommended"],
  {
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/preserve-manual-memoization": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
