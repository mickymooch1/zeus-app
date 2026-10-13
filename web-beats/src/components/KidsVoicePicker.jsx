import { ACCENT_OPTIONS, accentOptionLabel } from '../utils/genres';

// Kids song mode accent picker — shared by SongsPage's kids section and the /kids/song
// page so the two can't drift. Value is an ACCENT_OPTIONS key, sent as `vocal_accent`.
export default function KidsVoicePicker({ value, onChange, labelStyle, selectProps = {} }) {
  return (
    <>
      <p style={labelStyle}>🎤 Singer's Voice</p>
      <select value={value} onChange={(e) => onChange(e.target.value)} {...selectProps}>
        <option value="">🌟 Default</option>
        {ACCENT_OPTIONS.map((o) => (
          <option key={o.key} value={o.key}>{accentOptionLabel(o)}</option>
        ))}
      </select>
    </>
  );
}
