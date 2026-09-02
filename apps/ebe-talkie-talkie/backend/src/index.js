import { empty } from "./utils.js";
export { SocialStore } from "./social-store.js";

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return empty();
    return env.SOCIAL.getByName("global").fetch(request);
  },
};
