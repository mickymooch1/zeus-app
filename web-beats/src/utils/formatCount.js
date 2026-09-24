// Compact stat formatting (12.4K, 1.2M) matching the approved mockups' style
// for like/remix/view counts across the feed, clip page and profile.
export function formatCount(n) {
  const num = Number(n) || 0;
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  return String(num);
}
