import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';

const SECTIONS = [
  {
    icon: '🎵',
    title: 'Creating Your First Song',
    steps: [
      'Click Songs in the menu',
      'Pick a genre from the colour-coded pills',
      'Optional: describe your song or leave blank',
      'Click Generate',
      'Wait about 2 minutes for your song',
    ],
  },
  {
    icon: '🎭',
    title: 'Cover This Song',
    steps: [
      'Click "Cover This Song" on any of your tracks',
      'Enter your own lyrics',
      'Zeus creates a new version in the same style with your words',
    ],
  },
  {
    icon: '🎚️',
    title: 'Stem Separator',
    steps: [
      'Click "Get Stems" on any song',
      'Costs 1 premium credit',
      'Download vocals, drums, bass and instrumental separately',
      'Perfect for remixing or freestyling',
    ],
  },
  {
    icon: '🎛️',
    title: 'DJ Mixer',
    steps: [
      'Mix two of your songs together',
      'Use the crossfader to blend',
      'Record your mix as a single track',
      'Works in landscape mode on mobile',
    ],
  },
  {
    icon: '📋',
    title: 'Playlists',
    steps: [
      'Create custom playlists from your library',
      'Use AI Playlist to auto-generate based on a mood',
      'Auto-play next song',
      'Shuffle and repeat modes',
    ],
  },
  {
    icon: '🌍',
    title: 'Discover Feed',
    steps: [
      'Browse public songs from other users',
      'Like songs to personalise your "For You" feed',
      'Share any song link on social media',
    ],
  },
  {
    icon: '📱',
    title: 'Publish Your Music',
    steps: [
      'YouTube: one-click upload to your channel',
      'Facebook: auto-posts to your page',
      'Instagram: download MP3 to share',
      'Telegram: post to @zeusbeatsmusic',
    ],
  },
  {
    icon: '💎',
    title: 'Plans & Credits',
    steps: [
      'Free: 3 songs on signup',
      'Music Starter £9: 60 song versions/month + 3 premium credits',
      'Music Pro £19: 150 song versions/month + 10 premium credits',
      'Music Agency £39: 300 song versions/month + 20 premium credits',
      'Pay as you go: from £0.99',
    ],
  },
];

export default function TutorialPage() {
  return (
    <div style={{ minHeight: '100vh', background: '#000', color: '#fff' }}>
      <BeatsDashboardHeader />
      <main style={{ maxWidth: 780, margin: '0 auto', padding: '40px 16px 80px' }}>
        <h1 style={{ textAlign: 'center', fontSize: 'clamp(1.5rem, 5vw, 2.4rem)', marginBottom: 8, color: '#fff', fontWeight: 800, letterSpacing: '-0.5px' }}>
          ⚡ How To Use Zeus Beats
        </h1>
        <p style={{ textAlign: 'center', color: 'rgba(255,255,255,0.55)', marginBottom: 40, fontSize: '0.95rem' }}>
          Everything you need to create, remix and publish AI music
        </p>

        <div style={{ display: 'grid', gap: 20 }}>
          {SECTIONS.map(({ icon, title, steps }) => (
            <div
              key={title}
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(0,240,255,0.18)',
                borderRadius: 14,
                padding: '24px 28px',
                boxShadow: '0 0 20px rgba(0,240,255,0.04)',
              }}
            >
              <h2 style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: '1.15rem',
                fontWeight: 700,
                color: '#00f0ff',
                marginBottom: 16,
              }}>
                <span style={{ fontSize: '1.4rem' }}>{icon}</span>
                {title}
              </h2>
              <ol style={{ margin: 0, padding: '0 0 0 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {steps.map((step, i) => (
                  <li key={i} style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.95rem', lineHeight: 1.55 }}>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
