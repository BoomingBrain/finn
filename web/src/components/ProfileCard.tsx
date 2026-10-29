import type { PersonProfile } from "../api/types";
import { Clamp } from "./Clamp";

const CHANGE: Record<PersonProfile["change"], string> = { appointed: "Appointed", resigned: "Resigned", retired: "Retired" };

export function ProfileCard({ profile, filingUrl }: { profile: PersonProfile | null; filingUrl: string | null }) {
  if (!profile)
    return (
      <p className="mt-2 text-[13px] text-muted">
        No profile in filing.{" "}
        {filingUrl && <a href={filingUrl} target="_blank" rel="noreferrer" className="text-notable">Read the filing</a>}
      </p>
    );
  return (
    <div className="mt-2.5 rounded-md bg-surface px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 font-semibold">{profile.name}</p>
        <span className="shrink-0 text-[12px] text-muted">
          {CHANGE[profile.change]}
          {profile.effective_date ? ` ${profile.effective_date}` : ""}
        </span>
      </div>
      {profile.role && <p className="text-[13px] text-muted">{profile.role}</p>}
      {profile.background && <Clamp text={profile.background} className="mt-1.5 text-[14px]" />}
      {profile.prior_roles.length > 0 && (
        <p className="mt-1.5 text-[12px] text-muted">Previously {profile.prior_roles.slice(0, 2).join("; ")}</p>
      )}
    </div>
  );
}
