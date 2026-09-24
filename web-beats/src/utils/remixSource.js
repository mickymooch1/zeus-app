// What the remix confirm page shows, from either a clip (GET /api/clips/:id) or a
// Discover song (GET /api/discover/:id) — see ClipRemixPage.
export function toRemixSource(data, { isSong, backendUrl }) {
  const d = data || {};
  let visualUrl;
  if (isSong) visualUrl = d.cover_url || null;
  else if (d.media_type === 'cover') visualUrl = d.song_cover_url || null;
  else visualUrl = d.media_url ? `${backendUrl}${d.media_url}` : null;
  return {
    title: (isSong ? d.title : d.song_title) || '',
    visualUrl,
    genreTag: d.genre_tag || '',
    style: d.remix_style_descriptors || '',
    theme: d.remix_theme || '',
  };
}
