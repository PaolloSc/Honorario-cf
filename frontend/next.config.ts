import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app, silencing the multiple-lockfiles
  // inference warning caused by a stray package-lock.json in a parent dir.
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
