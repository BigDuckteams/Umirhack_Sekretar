import { useEffect, useState } from "react";

export interface NavScrollState {
  /** панель уехала вверх: прокрутка вниз */
  hidden: boolean;
  /** страница прокручена: панель становится компактнее */
  compact: boolean;
}

/** Панель прячется при прокрутке вниз и возвращается при движении вверх (актуально там, где страница прокручивается: телефон, узкие окна). */
export function useNavScroll(): NavScrollState {
  const [state, setState] = useState<NavScrollState>({ hidden: false, compact: false });

  useEffect(() => {
    let last = window.scrollY;
    let ticking = false;
    const frame = () => {
      const y = window.scrollY;
      const dy = y - last;
      setState((s) => {
        const compact = y > 8;
        let hidden = s.hidden;
        if (y < 80) hidden = false;
        else if (dy > 6) hidden = true;
        else if (dy < -6) hidden = false;
        return compact === s.compact && hidden === s.hidden ? s : { hidden, compact };
      });
      last = y;
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(frame);
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return state;
}
