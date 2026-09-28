// What the Clips "⋯" sheet offers (ClipMoreMenu.jsx). Everyone can copy the
// link; the creator can delete their own clip; anyone else can report it.
export function clipMenuItems({ isOwn }) {
  return isOwn ? ['copy', 'delete'] : ['copy', 'report'];
}

export function isOwnClip(user, clip) {
  return !!(user?.id && clip?.user_id && String(user.id) === String(clip.user_id));
}

// Same canonical URL ClipPage's Share button uses.
export function clipLink(clipId) {
  return `https://zeusbeats.com/clips/${clipId}`;
}
