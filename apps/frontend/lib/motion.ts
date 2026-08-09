import type { Variants } from "framer-motion";

export const EASE_SPRING = [0.16, 1, 0.3, 1] as const;
export const EASE_OUT    = [0.0,  0.0, 0.2, 1] as const;
export const EASE_INOUT  = [0.4,  0.0, 0.2, 1] as const;

export const spring = {
  gentle: { type: "spring" as const, stiffness: 120, damping: 20 },
  snappy: { type: "spring" as const, stiffness: 300, damping: 28 },
  bouncy: { type: "spring" as const, stiffness: 400, damping: 22 },
} as const;

export const fadeUp: Variants = {
  hidden:  { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE_SPRING } },
};

export const fadeIn: Variants = {
  hidden:  { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.35 } },
};

export const scaleIn: Variants = {
  hidden:  { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: spring.snappy },
};

export const stagger: Variants = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.09, delayChildren: 0.05 } },
};

export const slideRight: Variants = {
  hidden:  { opacity: 0, x: 24 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.5, ease: EASE_SPRING } },
};

export const slideLeft: Variants = {
  hidden:  { opacity: 0, x: -24 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.5, ease: EASE_SPRING } },
};

export const drawerVariants: Variants = {
  hidden:  { x: "100%", opacity: 0 },
  visible: { x: 0, opacity: 1, transition: spring.gentle },
  exit:    { x: "100%", opacity: 0, transition: { duration: 0.22, ease: EASE_INOUT } },
};
