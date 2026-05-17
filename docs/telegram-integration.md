# Telegram Bot Integration

Zeus can post messages and images to a Telegram channel via the `PostToTelegram` agent tool and the `POST /api/telegram/post` REST endpoint.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts (choose a name and username)
3. BotFather will reply with your **bot token** — looks like `123456789:ABCdefGhIJKlmNoPQRstuVWXyz`
4. Copy it — you'll add it to Railway in step 4

### 2. Create or choose a Telegram Channel

- Create a new channel in Telegram (or use an existing one)
- It can be public (`@yourchannelname`) or private (numeric ID)

### 3. Add the Bot as a Channel Admin

1. Open your channel → **Manage Channel** → **Administrators**
2. Add your bot as an administrator
3. Give it at minimum the **Post Messages** permission

### 4. Get the Channel ID

**Public channels:** the ID is simply `@yourchannelname` (include the `@`).

**Private channels:**
1. Forward any message from the channel to **@userinfobot**
2. It will reply with the channel's numeric ID (e.g. `-1001234567890`)

### 5. Add to Railway Environment Variables

In your Railway service → **Variables**, add:

| Variable | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `123456789:ABCdefGhIJKlmNoPQRstuVWXyz` |
| `TELEGRAM_CHANNEL_ID` | `@yourchannelname` or `-1001234567890` |

Redeploy the service after adding the variables.

## Usage

### Via Zeus Agent (chat)

Say things like:
- *"Post our new song 'Midnight Rain' to Telegram"*
- *"Post a Telegram update about today's website launch"*
- *"Post this to Telegram with an image"*

Zeus will draft the message, ask for confirmation, then call `PostToTelegram`.

### Auto-post on song generation

The `PostToTelegram` tool is available to Zeus during any conversation. You can ask Zeus to post song announcements automatically after generation.

### Via REST API

```http
POST /api/telegram/post
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "🎵 New track out now — <b>Midnight Rain</b>",
  "image_url": "https://example.com/cover.jpg"
}
```

**Fields:**
- `message` (required) — text to post; supports HTML (`<b>`, `<i>`, `<a href="...">`)
- `image_url` (optional) — if provided, sends a photo with `message` as the caption

**Response:**
```json
{ "ok": true, "detail": "✅ Posted to Telegram channel." }
```

## How it works

- Text-only → Telegram `sendMessage` API
- With image → Telegram `sendPhoto` API (message becomes the caption)
- HTML parse mode is enabled so you can use `<b>bold</b>`, `<i>italic</i>`, links etc.
- Maximum message length: 4096 characters (Telegram limit)
