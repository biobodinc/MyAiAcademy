import type { ProfileCreate } from "@myai/api-client";

export const INTEREST_OPTIONS = [
  "coding",
  "writing",
  "video",
  "music",
  "images",
  "research",
  "science",
  "games",
] as const;

export interface ProfileFormValues {
  name: string;
  owner_name: string;
  personality: string;
  communication_style: string;
  interests: string[];
  goals: string[];
}

export function toCreatePayload(v: ProfileFormValues): ProfileCreate {
  return {
    name: v.name.trim(),
    owner_name: v.owner_name.trim(),
    personality: v.personality.trim(),
    communication_style: v.communication_style.trim(),
    interests: v.interests,
    goals: v.goals,
  };
}
