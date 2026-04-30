import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["192.168.1.10"],
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
