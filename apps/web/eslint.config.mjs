import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Next 16 ile eslint-config-next yerel flat config yayımlıyor; `FlatCompat`
// (`@eslint/eslintrc`) köprüsüne artık gerek yok. Kural seti aynı iki ön ayardan
// gelir: `core-web-vitals` (react, react-hooks, jsx-a11y, import, @next/next) ve
// `typescript` (typescript-eslint önerilenleri).
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Türkçe metinde kesme işareti (ör. "API'ye") yaygındır; escape zorunluluğu
      // gereksiz gürültü yaratır (ruff'ta RUF001-003'ü kapatmamıza paralel).
      "react/no-unescaped-entities": "off",
    },
  },
  globalIgnores([".next/**", "node_modules/**", "next-env.d.ts"]),
]);

export default eslintConfig;
