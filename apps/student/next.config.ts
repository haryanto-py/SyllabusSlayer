import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Transpile the workspace package (ships TS source).
  transpilePackages: ["@syllabusslayer/shared"],
};

export default nextConfig;
