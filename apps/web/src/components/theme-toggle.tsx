"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Tema anahtarı. Sunucu render'ında çözünmüş tema bilinmez; ikon yanlış
 * çizilip hydration'da zıplamasın diye monte olana kadar yer tutucu gösterilir.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <span aria-hidden className="size-8 shrink-0" />;
  }

  const dark = resolvedTheme === "dark";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={dark ? "Açık temaya geç" : "Koyu temaya geç"}
          onClick={() => setTheme(dark ? "light" : "dark")}
        >
          {dark ? <Sun strokeWidth={1.75} /> : <Moon strokeWidth={1.75} />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{dark ? "Açık tema" : "Koyu tema"}</TooltipContent>
    </Tooltip>
  );
}
