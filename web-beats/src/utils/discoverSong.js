// A Discover song (GET /api/discover, /api/discover/:id) in the shape the clip
// creator uses for a library song — so "Create Clip" on Discover can open the
// creator with any public song, not just your own. Discover only lists public
// songs, hence is_public: 1 (no "publishing will make this public" notice).
export function discoverSongToClipSong(d) {
  if (!d) return null;
  return {
    variant_id: d.variant_id,
    title: d.title,
    image_url: d.cover_url,
    mp3_url: d.mp3_url,
    duration_seconds: d.duration_seconds,
    genre_tag: d.genre_tag,
    artist_name: d.artist_name,
    is_public: 1,
  };
}
