import type { PersonProfile } from "../api/types";

const CHANGE: Record<PersonProfile["change"], string> = { appointed: "Appointed", resigned: "Resigned", retired: "Retired" };

export function ProfileCard({ profile, filingUrl }: { profile: PersonProfile | null; filingUrl: string | null }) {
  const noProfile = (
    <p className="mt-2 text-[13px] text-muted">
      No profile in filing.{" "}
      {filingUrl && (
        <a href={filingUrl} target="_blank" rel="noreferrer" className="text-notable underline-offset-2 hover:underline">
          Read the filing
        </a>
      )}
    </p>
  );
  if (!profile) return noProfile;
  return (
    <div className="mt-3">
      <p>
        <span className="font-semibold">{profile.name}</span>
        {profile.role && <span className="text-muted">, {profile.role}</span>}
      </p>
      <p className="text-[13px] text-muted">
        {CHANGE[profile.change]}
        {profile.effective_date ? ` with effect from ${profile.effective_date}` : ""}
      </p>
      {profile.background ? <p className="mt-2">{profile.background}</p> : noProfile}
      {profile.prior_roles.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-[13px] text-muted">
          {profile.prior_roles.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}
    </div>
  );
}
