import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app, silencing the multiple-lockfiles
  // inference warning caused by a stray package-lock.json in a parent dir.
  outputFileTracingRoot: path.join(__dirname),
  // A calculadora de honorários é um HTML autocontido em public/calculadora/.
  // O rewrite só encurta a URL; o middleware já a protege por Azure AD.
  async rewrites() {
    return [{ source: "/calculadora", destination: "/calculadora/index.html" }];
  },
};

export default nextConfig;
