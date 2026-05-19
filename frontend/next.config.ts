import type { NextConfig } from "next";
import withPWAInit from "@ducanh2912/next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
});

const nextConfig: NextConfig = {
  // Rewrites removed to bypass proxy issues (ECONNRESET)
  // The frontend now directly fetches from NEXT_PUBLIC_API_URL
};

export default withPWA(nextConfig);
