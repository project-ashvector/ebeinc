(() => {
  "use strict";

  const FUNNEL_ORIGIN = "https://ebmarah-laptop-ai.tail9b0b89.ts.net";

  function rewriteUrl(value) {
    const url = String(value || "");
    if (
      url.startsWith("https://stream.ebeinc.online/") ||
      url.startsWith("https://status.ebeinc.online/")
    ) {
      try {
        const parsed = new URL(url);
        return `${FUNNEL_ORIGIN}${parsed.pathname}${parsed.search}`;
      } catch (_error) {
        return url;
      }
    }
    return url;
  }

  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    if (typeof input === "string") {
      return nativeFetch(rewriteUrl(input), init);
    }
    if (input instanceof Request) {
      const rewritten = rewriteUrl(input.url);
      if (rewritten !== input.url) {
        return nativeFetch(new Request(rewritten, input), init);
      }
    }
    return nativeFetch(input, init);
  };

  if (window.Hls && window.Hls.prototype) {
    const nativeLoadSource = window.Hls.prototype.loadSource;
    window.Hls.prototype.loadSource = function loadSource(url) {
      return nativeLoadSource.call(this, rewriteUrl(url));
    };
  }

  window.ALLTHINGS140_FUNNEL = FUNNEL_ORIGIN;
})();
