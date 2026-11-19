import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Layers,
  ListTree,
  Maximize2,
  Minimize2,
  Minus,
  Moon,
  PanelRight,
  Pin,
  Plus,
  RotateCcw,
  Scan,
  Scissors,
  Settings,
  SquareDashedMousePointer,
  House,
  Sun,
  type LucideProps,
} from "lucide-react";

/**
 * The one icon set (Lucide, ISC licence: see THIRD_PARTY_NOTICES.txt), at one size and one stroke
 * weight, so icons beside each other match. An icon is never the only name of a control: every
 * icon button carries an `aria-label` (and a tooltip) where it is used.
 */
function icon(Glyph: React.ComponentType<LucideProps>) {
  return function Icon(props: LucideProps) {
    return <Glyph size={16} strokeWidth={1.75} aria-hidden="true" focusable="false" {...props} />;
  };
}

export const IconBack = icon(ArrowLeft);
export const IconUp = icon(ArrowUp);
export const IconHome = icon(House);
export const IconSettings = icon(Settings);
export const IconBoxSelect = icon(SquareDashedMousePointer);
export const IconPrune = icon(Scissors);
export const IconGrow = icon(Maximize2);
export const IconShrink = icon(Minimize2);
export const IconLeft = icon(ArrowLeft);
export const IconRight = icon(ArrowRight);
export const IconNudgeUp = icon(ArrowUp);
export const IconNudgeDown = icon(ArrowDown);
export const IconResetLayout = icon(RotateCcw);
export const IconPlus = icon(Plus);
export const IconPin = icon(Pin);
export const IconMinus = icon(Minus);
export const IconFit = icon(Scan);
export const IconHierarchy = icon(ListTree);
export const IconInspector = icon(PanelRight);
export const IconGraphs = icon(Layers);
export const IconSun = icon(Sun);
export const IconMoon = icon(Moon);
