/** @type {import('next').NextConfig} */
// NEXT_PUBLIC_STATIC=1 gera o site estático (GitHub Pages); sem isso, proxy /api para o Python local.
const isStatic = process.env.NEXT_PUBLIC_STATIC === "1";

const nextConfig = isStatic
  ? { output: "export", trailingSlash: true, basePath: process.env.NEXT_PUBLIC_BASE_PATH || "" }
  : { async rewrites() { return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }]; } };

export default nextConfig;
