# Local-first data

The browser keeps display name and selected avatar in localStorage. It transmits only that public display name, avatar identifier, random connection/session ID, chat/reaction events and technical connection address used transiently for abuse limits. The server stores at most 100 recent sanitized messages and aggregate reaction totals. Presence, speech bubbles, connection state and Room Energy are ephemeral. No legal name, email, phone, address, local password, payment information or radio-control secret is requested.
