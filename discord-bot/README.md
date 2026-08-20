# AllThings140 Radio Discord bot

Starter bot for the public AllThings140 Radio community. It provides `/radio`, `/invite`, `/nowplaying`, `/announce`, `/clear`, and a welcome message for new members.

## Run it

1. Install Node.js 20+.
2. Run `npm install` in this folder.
3. Copy `.env.example` to `.env` and set `DISCORD_TOKEN` privately. Keep `.env` out of Git.
4. Optionally set `WELCOME_CHANNEL_ID` to the channel where welcome messages should go.
5. Run `npm start`.

The bot must have View Channel, Send Messages, Embed Links, Read Message History, Manage Messages, and the **Server Members Intent** enabled in the Discord Developer Portal.
