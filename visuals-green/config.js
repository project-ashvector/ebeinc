window.AT140_GREEN_CONFIG={
  environment:"live",
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
  // Large media is served by the isolated Oracle staging media origin, never Pages.
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
