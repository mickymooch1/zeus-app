// Genre catalog — labels, category grid, and color/label helpers.
//
// Extracted from SongsPage.jsx (Task 14) so this data is a genuine leaf
// module with no importers of its own. Before this extraction, SongCard.jsx
// imported genreColor/gLabel back from SongsPage.jsx — a circular import that
// was safe only because SongCard had exactly one importer (SongsPage.jsx
// itself). The moment a second page (MemorialPage.jsx) imports SongCard, that
// circularity would pull ~4,300 lines of SongsPage.jsx into the new page's
// bundle. Moving the genre data here breaks the cycle entirely: both
// SongsPage.jsx and SongCard.jsx now import from this file instead of from
// each other.
//
// genres.test.mjs text-scans this file (not SongsPage.jsx) for a literal
// "const GENRE_CATEGORIES = [...]" declaration, so the category data must
// stay physically here.
export const GENRE_LABEL = { bluegrass:'Bluegrass', countryballad:'Country Ballad', britpop:'Britpop', indierock:'Indie Rock', folk:'Folk', acousticballad:'Acoustic Ballad', folkblues:'Folk Blues', roots:'Roots', acousticblues:'Acoustic Blues', patriotic:'Patriotic', hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk', celticpunk:'Celtic Punk', rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage', jungle:'Jungle', bassline:'Bassline House', house:'House', deephouse:'Deep House', dancehouse:'Dance House', loversrock:'Lovers Rock', ukdrill:'UK Drill', kpop:'K-Pop', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul', technhouse:'Tech House', driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub', dancehall:'Dancehall', deeprotbassline:'Deeprot Bassline', jazz:'Jazz', swing:'Swing', vocaljazz:'Vocal Jazz', scat:'Scat Jazz', opera:'Opera', electronicfunk:'Electronic Funk', syntheticpop:'Synthetic Pop', ragga:'Ragga', dubstep:'Dubstep', bhangra:'Bhangra', rockney:'Rockney', metal:'Metal', bluesrock:'Blues Rock', hardrock:'Hard Rock', punkrock:'Punk Rock', reggaeton:'Reggaeton', latintrap:'Latin Trap', rootsreggae:'Roots Reggae', countryamericana:'Country Americana', countrypop:'Country Pop', southemsoul:'Southern Soul', soulrnb:'Soul R&B', orchestralsoul:'Orchestral Soul', classicfunk:'Classic Funk', traditionalpop:'Traditional Pop', rocknroll:'Rock & Roll', trap:'Trap', eastcoasthiphop:'East Coast Hip-Hop', westcoasthiphop:'West Coast Hip-Hop', poprap:'Pop Rap', synthwave:'Synthwave', trance:'Trance', triphop:'Trip-Hop', salsa:'Salsa', gospel:'Gospel', hymns:'Hymns', trapsoul:'Trap Soul', meditation:'Meditation', ambient:'Ambient', christmas:'Christmas', corridos:'Corridos', healingfrequency:'Healing Frequencies', naturesounds:'Nature Sounds', whalesong:'Whale Song', cracklingfire:'Crackling Fire', thunderstorm:'Thunderstorm', oceanwaves:'Ocean Waves', forest:'Forest', nightsounds:'Night Sounds', purebassline:'Pure Bassline', psychedelicguitar:'Psychedelic Guitar', saxophone:'Saxophone', pianosolo:'Piano', violinsolo:'Violin', electricbluesguitar:'Blues Guitar', trumpet:'Trumpet', flamencoguitar:'Flamenco Guitar', disco:'Disco', nudisco:'Nu Disco', bollywood:'Bollywood', boombap:'Boom Bap', citypop:'City Pop', futurebass:'Future Bass', gqom:'Gqom', gogo:'Go-Go' };
export const GENRE_CATEGORIES = [
  { id: 'uk_street',  label: '🎤 UK Street & Hip Hop', color: '#00f0ff',
    genres: ['grime','ukdrill','afroswing','bassline','ukgarage','niche','drumandbass','jungle','deeprotbassline','ukstreetsoul','triphop'] },
  { id: 'soul',       label: '🎵 Soul & Blues',        color: '#fb923c',
    genres: ['soul','bluessoul','southemsoul','soulrnb','orchestralsoul','classicfunk','gogo','gospel','hymns','trapsoul','vocaljazz','scat','swing','rnb','blues','deepsoulblues'] },
  { id: 'rock',       label: '🎸 Rock & Metal',        color: '#f87171',
    genres: ['rock','hardrock','metal','punkrock','rocknroll','traditionalpop','bluesrock','indie','britpop','indierock','rockney'] },
  { id: 'country_folk', label: '🤠 Country & Folk',    color: '#d97706',
    genres: ['country','traditionalcountry','bluegrass','countryamericana','countrypop','countryballad','folk','acousticballad','folkblues','roots','acousticblues','celticpunk'] },
  { id: 'electronic', label: '🎹 Electronic & Dance',  color: '#4ade80',
    genres: ['house','technhouse','deephouse','dancehouse','purebassline','synthwave','driftphonk','techno','trance','edm','electronicfunk','dubstep','jerseyclub','hyperpop','syntheticpop','disco','nudisco','futurebass'] },
  { id: 'world',      label: '🌍 World & Urban',       color: '#fbbf24',
    genres: ['afrobeats','reggae','rootsreggae','reggaeton','ragga','dancehall','corridos','salsa','bhangra','loversrock','rastadub','amapiano','latintrap','gqom','bollywood'] },
  { id: 'pop',        label: '🎶 Pop & Hip Hop',       color: '#f472b6',
    genres: ['pop','patriotic','trap','eastcoasthiphop','westcoasthiphop','poprap','kpop','hiphop','boombap','citypop'] },
  { id: 'chill',      label: '🧘 Chill & Wellness',    color: '#e2e8f0',
    genres: ['lofi','meditation','ambient','healingfrequency','naturesounds','whalesong','cracklingfire','thunderstorm','oceanwaves','forest','nightsounds','classical','opera','acoustic','jazz','irishfolk','irishjig','christmas'] },
  { id: 'instrumental_solo', label: '🎷 Instrumental & Solo', color: '#a78bfa',
    genres: ['saxophone','pianosolo','violinsolo','electricbluesguitar','psychedelicguitar','trumpet','flamencoguitar'] },
];

// genreColor/gLabel are exported so both SongsPage.jsx and SongCard.jsx (which
// each render a genre pill) can share this single source of truth instead of
// duplicating it.
const _genreColorMap = Object.fromEntries(
  GENRE_CATEGORIES.flatMap(cat => cat.genres.map(g => [g, cat.color]))
);
export const genreColor = (g) => {
  if (!g) return '#cccccc';
  const base = g.includes('__') ? g.split('__')[0] : g;
  return _genreColorMap[base] || '#cccccc';
};
export const gLabel = (g) => {
  if (!g) return '';
  if (g.includes('__')) {
    const [a, b] = g.split('__');
    const la = GENRE_LABEL[a] || a.charAt(0).toUpperCase() + a.slice(1);
    const lb = GENRE_LABEL[b] || b.charAt(0).toUpperCase() + b.slice(1);
    return `${la} × ${lb}`;
  }
  return GENRE_LABEL[g] || g.charAt(0).toUpperCase() + g.slice(1);
};

// Every genre the category grid can select, derived from that grid rather than
// hand-maintained alongside it. It used to be a second literal list, and the two
// drifted: it held 71 of the 107 pickable genres, so 36 — trance, salsa, ambient,
// folk, bluegrass, hardrock, punkrock, britpop, westcoasthiphop, every
// nature-sound and every instrumental-solo entry — could be chosen as a primary
// genre but never offered as Genre B in a blend, despite the backend supporting
// them fine. Deriving it means the grid is the single source of truth and the two
// cannot disagree again. genres.test.mjs pins this list to the backend's
// GENRE_PRESETS keys so a genre can never be pickable without a style preset.
export const GENRES = [...new Set(GENRE_CATEGORIES.flatMap(cat => cat.genres))];
