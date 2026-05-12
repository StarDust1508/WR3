// @ts-expect-error — `@opennextjs/cloudflare` ships its types lazily; the
// helper is only used here, no runtime impact.
import { defineCloudflareConfig } from "@opennextjs/cloudflare";

/**
 * OpenNext.js adapter configuration for Cloudflare Workers.
 *
 * The default config (no overrides) maps the Next.js app to:
 *   - a single Worker entry at `.open-next/worker.js`
 *   - static assets under `.open-next/assets`
 *
 * `wrangler.toml` in the same folder ties those outputs to the Workers
 * runtime via an ASSETS binding.
 */
export default defineCloudflareConfig({});
