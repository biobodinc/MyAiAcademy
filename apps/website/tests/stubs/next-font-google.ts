/**
 * `next/font/google` is a build-time transform, not a real module: the Next compiler
 * rewrites each call into a generated font object. Under vitest nothing performs that
 * rewrite, so the import resolves to a namespace with no callable members and `layout.tsx`
 * throws on load.
 *
 * This stub stands in for it, returning the same shape the compiler would — enough for a
 * test that renders the layout or reads its metadata. It deliberately does not attempt to
 * load real fonts: nothing under jsdom would render them.
 */
interface StubbedFont {
  className: string;
  variable: string;
  style: { fontFamily: string };
}

const font = (): StubbedFont => ({
  className: "stub-font",
  variable: "stub-font-variable",
  style: { fontFamily: "stub" },
});

export const Instrument_Serif = font;
export const IBM_Plex_Sans = font;
export const IBM_Plex_Mono = font;
