"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState, type ReactNode } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";

/**
 * İstemci sağlayıcıları: tema · sunucu durumu · tooltip.
 *
 * Tema varsayılanı light (BRIEF `tema`): ana çalışma yüzeyi beyaz bir PDF
 * tuvali; koyu kabuk + beyaz tuval kontrast sıçraması göz yorar. Koyu tema
 * tam desteklenir, varsayılan değildir.
 *
 * `nonce`: `next-themes` ilk boyamada temayı ayarlamak için satır içi bir
 * betik gömüyor. Zorlayıcı CSP altında o betik nonce olmadan çalışmaz — ve
 * çalışmazsa koyu tema kullanıcısı her yüklemede bir kare beyaz görür.
 */
export function Providers({ children, nonce }: { children: ReactNode; nonce?: string }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem
      disableTransitionOnChange
      nonce={nonce}
    >
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
