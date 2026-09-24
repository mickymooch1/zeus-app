import { useLayoutEffect } from 'react';

/**
 * Publishes an element's rendered height as a CSS custom property on <html>
 * (0px when unmounted/hidden), kept live with a ResizeObserver — so fixed
 * chrome (a header, a playback bar) can be cleared by layouts that read the
 * variable, at any text size. Same pattern as CookieBanner / ClipsBottomNav.
 * `present`: pass whether a conditionally-rendered element is mounted, so the
 * height is re-measured when it appears (and reset to 0 when it goes).
 */
export function usePublishedHeight(ref, varName, present = true, extra = 0) {
  useLayoutEffect(() => {
    const root = document.documentElement;
    const el = ref.current;
    if (!el) { root.style.setProperty(varName, '0px'); return undefined; }
    const publish = () => root.style.setProperty(varName, `${el.offsetHeight + extra}px`);
    publish();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(publish) : null;
    ro?.observe(el);
    return () => { ro?.disconnect(); root.style.setProperty(varName, '0px'); };
  }, [ref, varName, present, extra]);
}
