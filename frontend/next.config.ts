import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app, silencing the multiple-lockfiles
  // inference warning caused by a stray package-lock.json in a parent dir.
  outputFileTracingRoot: path.join(__dirname),

  // /jesp e' como o escritorio chama o contrato de acao de consumo.
  async redirects() {
    return [{ source: "/jesp", destination: "/consumidor", permanent: false }];
  },
};

export default nextConfig;
