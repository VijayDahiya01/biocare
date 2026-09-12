/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Proxy API calls to the backend (same-origin from the browser, so cookies
    // and CSRF "just work"). Override the target for host dev with API_PROXY,
    // e.g. API_PROXY=http://localhost:8080. In prod, nginx handles routing.
    const target = process.env.API_PROXY || "http://api:8080";
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
};
module.exports = nextConfig;
