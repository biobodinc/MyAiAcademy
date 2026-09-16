import { SITE } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-border">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-8 text-sm text-fg-muted sm:flex-row sm:items-baseline sm:justify-between sm:px-6">
        <p className="display text-base text-fg">
          Private by default. Local by design. Sharing by choice.
        </p>
        <p className="datum">
          <a
            className="underline underline-offset-4 transition-colors hover:text-fg"
            href={`https://github.com/${SITE.githubRepo}`}
            rel="noopener noreferrer"
          >
            Source on GitHub
          </a>
          {" · "}Apache-2.0
        </p>
      </div>
    </footer>
  );
}
