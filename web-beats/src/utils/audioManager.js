// Singleton that ensures only one audio source plays at a time across the app.
// Handles both HTMLAudioElement (NowPlayingContext, DiscoverPage) and
// WaveSurfer instances (SongsPage in-card player).

let currentAudio = null;       // HTMLAudioElement
let currentWaveSurfer = null;  // WaveSurfer instance
let currentVariantId = null;

export const audioManager = {
  // Use for HTMLAudioElement sources. Stops any WaveSurfer, pauses previous
  // audio element, then plays the new one.
  play(audio, variantId) {
    if (currentWaveSurfer) {
      currentWaveSurfer.pause();
      currentWaveSurfer = null;
    }
    if (currentAudio && currentAudio !== audio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    }
    currentAudio = audio;
    currentVariantId = variantId;
    audio.play().catch(() => {});
  },

  // Use for WaveSurfer. Stops any HTML audio source, pauses previous WaveSurfer.
  // Does NOT call ws.play() — the caller does that after registering.
  playWaveSurfer(ws, variantId) {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
      currentAudio = null;
    }
    if (currentWaveSurfer && currentWaveSurfer !== ws) {
      currentWaveSurfer.pause();
    }
    currentWaveSurfer = ws;
    currentVariantId = variantId;
  },

  // Stop and deregister whatever is currently playing.
  stop() {
    if (currentWaveSurfer) {
      currentWaveSurfer.pause();
      currentWaveSurfer = null;
    }
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
      currentAudio = null;
    }
    currentVariantId = null;
  },

  // Stop only WaveSurfer — used at crossfade start so the primary HTMLAudioElement
  // is not interrupted while it begins fading out.
  stopWaveSurfer() {
    if (currentWaveSurfer) {
      currentWaveSurfer.pause();
      currentWaveSurfer = null;
    }
  },

  // Update the tracked variant ID without touching playback — called after crossfade
  // completes so getCurrentId() returns the new song without triggering a play().
  updateVariantId(variantId) {
    currentVariantId = variantId;
  },

  getCurrentId() {
    return currentVariantId;
  },
};
