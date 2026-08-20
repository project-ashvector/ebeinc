# Advertising architecture roadmap

## Current system

The authoritative scheduler can insert station announcements/ads into the free broadcast. Campaign configuration must remain centralized on the server, not in listener clients. Initial inventory should favor station-created promos and limited relevant sponsors.

## Campaign model

Track sponsor ID, creative ID, audio asset, duration, start/end, status, priority, station-promo versus paid type, play log, maximum plays/hour, minimum songs between breaks, maximum consecutive ads, frequency caps, and takeover exclusion. Defaults should protect music programming; exact commercial rules remain administrator-configurable rather than hardcoded.

## Sales workflow

Inquiry → fit/rights review → creative technical review → campaign configuration → preview/approval → scheduled activation → verified play logging → report. Pricing and audience claims remain blank until real measurements exist.

## Premium future

A client-side switch cannot remove audio already encoded into one stream. A genuine ad-free tier requires two synchronized server outputs: a free program output with commercial breaks and an entitlement-protected premium output that substitutes music/station IDs on the same programming clock. Use expiring authorized playback sessions; never publish a permanent premium URL. Subscription billing later requires verified provider webhooks, account/authentication, entitlement expiry/cancellation and privacy/terms work. No subscription charge is activated in this release.
