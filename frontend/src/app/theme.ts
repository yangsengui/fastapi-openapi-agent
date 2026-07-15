import type { CSSProperties } from "react";

import type { ThemePreset } from "../types";

const themes = {
  default: {
    panel: "#fbfaf7",
    fg: "#1f2328",
    muted: "#77736c",
    accent: "#1f2328",
    accentFg: "#ffffff",
    soft: "rgba(31,35,40,0.06)",
    border: "rgba(31,35,40,0.10)",
  },
  ocean: {
    panel: "#f6fffd",
    fg: "#083f3b",
    muted: "#4f766f",
    accent: "#0f766e",
    accentFg: "#ecfeff",
    soft: "rgba(15,118,110,0.08)",
    border: "rgba(15,118,110,0.16)",
  },
} as const;

export function themeStyle(preset: ThemePreset): CSSProperties {
  const theme = themes[preset];
  return {
    "--foa-panel": theme.panel,
    "--foa-fg": theme.fg,
    "--foa-muted": theme.muted,
    "--foa-accent": theme.accent,
    "--foa-accent-fg": theme.accentFg,
    "--foa-soft": theme.soft,
    "--foa-border": theme.border,
  } as CSSProperties;
}
