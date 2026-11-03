/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // @vysel/ui ships TypeScript source; compile it with the app.
  transpilePackages: ['@vysel/ui'],
  // Same-origin proxy to FastAPI: the browser only ever talks to this app, so no CORS
  // and auth cookies stay first-party. API_URL defaults to the local Uvicorn server.
  async rewrites() {
    const api = process.env.API_URL ?? 'http://localhost:8000';
    return [{ source: '/api/v1/:path*', destination: `${api}/v1/:path*` }];
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(self), microphone=(), geolocation=()' },
          { key: 'X-Frame-Options', value: 'DENY' },
        ],
      },
    ];
  },
};

export default nextConfig;
