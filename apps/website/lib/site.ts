export const SITE = {
  name: "MyAI Academy",
  tagline: "Build it. Teach it. Make it yours.",
  description:
    "A personal AI you build, teach, train, specialize and carry across your devices. Private by default, local by design, sharing by choice.",
  url: process.env.NEXT_PUBLIC_SITE_URL?.trim() || "http://localhost:3000",
  githubRepo: process.env.NEXT_PUBLIC_GITHUB_REPO?.trim() || "biobodinc/MyAiAcademy",
} as const;
