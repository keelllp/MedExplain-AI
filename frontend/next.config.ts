import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow an isolated build dir so a second dev server (e.g. the Playwright E2E stack on a
  // different port) doesn't fight the main `next dev` over the same .next directory.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
};

export default nextConfig;
