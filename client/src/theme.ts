import { createLightTheme } from "@fluentui/react-components";
import type { BrandVariants, Theme } from "@fluentui/react-components";

/** Signal-red brand ramp (hue ~357°) — matches the red+white identity heavy
 * equipment/industrial brands use (Manitou's own site included). 10 darkest
 * to 160 lightest, per Fluent UI's BrandVariants convention. Generated via
 * HSL sweep, not hand-picked, so the steps stay perceptually even. */
export const monitouBrand: BrandVariants = {
  10: "#2b0809",
  20: "#470b0e",
  30: "#5f0c10",
  40: "#790c11",
  50: "#920c13",
  60: "#ad0b13",
  70: "#cb0b14",
  80: "#e40c17",
  90: "#f01924",
  100: "#ef3942",
  110: "#ee636a",
  120: "#ec9397",
  130: "#edbbbd",
  140: "#efd7d8",
  150: "#f4ebec",
  160: "#f8f6f7",
};

/** Clean white/red light theme — red accent on white/light-gray surfaces,
 * dark text. */
export const monitouTheme: Theme = createLightTheme(monitouBrand);
