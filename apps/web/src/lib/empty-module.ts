// Boş modül — `next.config.ts`teki Turbopack `resolveAlias` hedefi.
//
// pdfjs-dist, Node'da sayfa çizmek için opsiyonel `canvas` paketini ister;
// tarayıcıda gerekmez ve kurulumda bilinçli olarak derlenmez
// (`pnpm-workspace.yaml` → `allowBuilds.canvas: false`). Webpack'te
// `resolve.alias.canvas = false` ile susturuluyordu; Turbopack'te `false`
// karşılığı yok, takma ad bu boş modüle yönlendirilir (react-pdf'in Next
// önerisi).
export {};
