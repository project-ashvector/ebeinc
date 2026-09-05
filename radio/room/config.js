window.AT140_GREEN_CONFIG={
  environment:"live",
  rendererRole:"green-room-renderer",
  realtimeUrl:"wss://visuals-realtime-staging.allthings140radio.online/ws?environment=live",
  chatUrl:location.hostname.endsWith(".ebeinc-uqt.pages.dev")
    ? "wss://allthings140-live-chat-phase-c.ebmarahofficial.workers.dev/ws"
    : "wss://chat.ebeinc.online/ws",
  realtimeStateUrl:"https://visuals-realtime-staging.allthings140radio.online/visuals-state?environment=live",
  realtimeLayoutUrl:"https://visuals-realtime-staging.allthings140radio.online/layout-state?environment=live",
  rendererAckUrl:"https://visuals-realtime-staging.allthings140radio.online/renderer-ack",
  workstationLiveUrl:"https://visuals-realtime-staging.allthings140radio.online/live-state?environment=live",
  radioStatusUrl:"https://status.ebeinc.online/api/public/status",
  playlistUrl:"./playlist.json",
  layoutUrl:"./layout.json",
  // Immutable workstation derivatives travel through the authenticated outbound
  // Cloudflare path; no residential port is exposed to viewers.
  mediaBaseUrl:"https://visuals-realtime-staging.allthings140radio.online/media",
  optimizedMediaBaseUrl:"https://visuals-realtime-staging.allthings140radio.online/media",
  mediaVersion:"20260816-2",
  routingUrl:"https://allthings140radio.online/api/visual-routing",
  legacyFallbackEnabled:true,
  legacyFallbackHls:"https://allthings140radio.online/assets/visuals-desktop-v8/index.m3u8",
  legacyFallbackDesktop:"https://allthings140radio.online/assets/visuals-desktop.mp4?v=7.0.0",
  legacyFallbackMobile:"https://allthings140radio.online/assets/phone-visuals-authoritative-v1.mp4?v=1.0.0",



  streamUrl:"https://stream.ebeinc.online/live.mp3"
};
