# Zeus Beats iOS — Stage 1 Design Spec

## Goal

Native iOS app for Zeus Beats built with Expo + TypeScript, buildable from Windows via EAS cloud builds (no Mac required). Stage 1 delivers: project scaffold, navigation shell, and a working Login screen that authenticates against the existing Railway backend.

## Scope

Stage 1 only:
- Expo project scaffold at `zeus-app/zeus-beats-ios/`
- React Navigation v7 shell: Login → Main Tabs (Create Song, Library — placeholder screens)
- Native Login screen: calls `/auth/login`, stores JWT in iOS Keychain via `expo-secure-store`, Zeus Beats neon branding

Out of scope for Stage 1: Create Song functionality, Library/Player functionality, push notifications, deep links, App Store submission.

---

## Architecture

### Location

`zeus-app/zeus-beats-ios/` — inside the existing monorepo alongside `web-beats/` and `backend/`, tracked in the same git repo.

### EAS Config

Reuse the existing EAS project ID and bundle identifier:
- Project ID: `1deffc7e-e3ef-4b9f-995d-0b05a576fc17`
- Bundle ID: `com.zeusbeats.app`
- EAS config (`eas.json`): production build profile, autoIncrement

### File Structure

```
zeus-beats-ios/
  app.json              # Expo config: projectId, bundleId, splash, icons
  eas.json              # EAS build profiles
  App.tsx               # Root: NavigationContainer + Stack navigator
  src/
    constants/
      theme.ts          # Colours, typography, spacing constants
      api.ts            # BACKEND_URL, endpoint paths
    context/
      AuthContext.tsx   # Token state, login(), logout(), boot check
    screens/
      LoginScreen.tsx   # Email + password, calls /auth/login
      CreateSongScreen.tsx  # Placeholder
      LibraryScreen.tsx     # Placeholder
    navigation/
      RootNavigator.tsx  # Stack: Login / Main (tabs)
      MainTabs.tsx       # Bottom tabs: Create Song, Library
```

---

## Auth Flow

**Login endpoint:** `POST https://zeus-app-production.up.railway.app/auth/login`

Request body: `{ email: string, password: string }`

Response: `{ token: string, user: { id, email, name, ... } }`

Error: `{ detail: string }`

**Token storage:** `expo-secure-store` (maps to iOS Keychain). Key: `zeus_beats_token`. More secure than AsyncStorage; hardware-backed on device.

**Boot sequence:**
1. App starts → `AuthContext` calls `SecureStore.getItemAsync('zeus_beats_token')`
2. If token found → validate with `GET /auth/me` (Bearer token)
3. If valid → navigate to Main tabs; if invalid/missing → show Login

**Logout:** `SecureStore.deleteItemAsync('zeus_beats_token')` → navigate to Login.

---

## Login Screen

### Visual Design

Matches the web app's cyberpunk aesthetic:

| Element | Value |
|---------|-------|
| Background | `#0b0b14` (deep dark) |
| Card background | `rgba(255,255,255,0.03)` with `1px solid rgba(0,240,255,0.15)` border |
| Logo | ⚡ (large, amber/yellow), "Zeus Beats" in bold white |
| Tagline | "AI music creation. No limits." in muted grey |
| Input fields | Dark fill `rgba(0,0,0,0.4)`, cyan border on focus `rgba(0,240,255,0.4)` |
| Primary button | Linear gradient `#7c3aed → #a855f7` (purple), white text, full width |
| Error | Red-tinted banner `rgba(239,68,68,0.12)`, red text |
| Loading | ActivityIndicator in cyan `#00f0ff` |

### Behaviour

- `KeyboardAvoidingView` wraps the form (iOS: `padding` mode)
- On submit: disable inputs, show spinner in button
- On success: `SecureStore.setItemAsync` → navigate to Main tabs
- On error: show error banner with message from `data.detail`
- On mount: check stored token; if present, skip login and navigate to Main

---

## Navigation

```
Stack (RootNavigator)
├── Login (headerShown: false)
└── Main (headerShown: false)
    └── Tabs (MainTabs)
        ├── CreateSong  (⚡ Create)
        └── Library     (🎵 Library)
```

Tab bar style: background `#120d2e`, active tint `#a78bfa`, inactive tint `#3a3a5a`, top border `rgba(255,255,255,0.08)`.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `expo` | SDK + build tooling |
| `expo-secure-store` | iOS Keychain JWT storage |
| `expo-linear-gradient` | Gradient button background |
| `expo-font` | Optional custom fonts |
| `@react-navigation/native` | Navigation container |
| `@react-navigation/stack` | Stack navigator (Login → Main) |
| `@react-navigation/bottom-tabs` | Tab navigator (Create, Library) |
| `react-native-screens` | Native screen optimisation |
| `react-native-safe-area-context` | Safe area insets |
| `react-native-gesture-handler` | Required by React Navigation |

---

## EAS Build

`eas.json` profiles:
- `preview`: internal distribution (TestFlight / direct IPA) — for testing before App Store
- `production`: App Store submission, autoIncrement build number

Build command (no Mac needed, cloud build): `eas build --platform ios --profile preview`
