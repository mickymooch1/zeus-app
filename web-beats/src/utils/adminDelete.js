// Admin panel "Delete account" (2026-09-29) — the rules the confirmation
// dialog enforces before its Delete button enables. The server re-checks all
// of them (account_deletion.delete_from_admin_panel); this only keeps the
// button honest.

export function canConfirmDelete({ preview, typedEmail, acknowledged, busy }) {
  if (!preview || busy) return false;
  if ((preview.blockers || []).length > 0) return false;
  if ((preview.warnings || []).length > 0 && !acknowledged) return false;
  return (typedEmail || '').trim().toLowerCase() === (preview.email || '').toLowerCase();
}

// Delete buttons are never offered for admin rows or for yourself (the server
// refuses both anyway).
export function showDeleteButton(row, me) {
  return !!row && !row.is_admin && row.id !== me?.id;
}

export function formatBytes(n) {
  if (!n) return '0 KB';
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
