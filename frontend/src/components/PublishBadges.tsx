// One badge per platform a snapshot was sent to: a live post (linked) wins over
// dry-runs, so a dry-run is never shown as a real publish.

import type { SnapshotPublish } from "../api/snapshots";

export default function PublishBadges({ publishes }: { publishes: SnapshotPublish[] }) {
  const platforms = [...new Set(publishes.map((p) => p.platform))];
  if (platforms.length === 0) return null;
  return (
    <>
      {platforms.map((platform) => {
        const live = publishes.find((p) => p.platform === platform && !p.dry_run);
        if (live) {
          return (
            <a
              key={platform}
              href={live.external_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full bg-emerald-600 px-2.5 py-0.5 text-xs font-medium text-white hover:bg-emerald-700"
            >
              Published · {platform}
            </a>
          );
        }
        const dryRuns = publishes.filter((p) => p.platform === platform).length;
        return (
          <span
            key={platform}
            className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800"
            title="Dry-run only: nothing was posted."
          >
            Dry-run · {platform}
            {dryRuns > 1 ? ` ×${dryRuns}` : ""}
          </span>
        );
      })}
    </>
  );
}
