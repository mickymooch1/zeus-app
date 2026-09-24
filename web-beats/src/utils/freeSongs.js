// The line under "Welcome to Zeus Beats" on /songs, from the user's REAL song
// balance (it used to hard-code 3). null → nothing worth saying; hide the card.
export function freeSongsLine(balance) {
  if (!Number.isFinite(balance) || balance <= 0) return null;
  return `You have ${balance} free song${balance === 1 ? '' : 's'} to get started.`;
}
