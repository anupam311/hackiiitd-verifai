/** @type {import('next').NextConfig} */

const backendUrl = process.env.BACKEND_URL;

const nextConfig = {
  reactStrictMode: true,

  async rewrites() {
    if (!backendUrl) {
      return [];
    }

    const backend = backendUrl.replace(/\/+$/, "");

    return [
      {
        source: "/auth/:path*",
        destination: `${backend}/auth/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
      {
        source: "/health/:path*",
        destination: `${backend}/health/:path*`,
      },
    ];
  },
};

export default nextConfig;