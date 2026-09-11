import { SITE } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="border-t border-border py-8 text-center text-xs text-fg-muted">
      <p>Private by default. Local by design. Sharing by choice.</p>
      <p className="mt-1">
        <a
          className="underline"
          href={`https://github.com/${SITE.githubRepo}`}
          rel="noopener noreferrer"
        >
          Source on GitHub
        </a>
        {" · "}Apache-2.0
      </p>
    </footer>
  );
}
