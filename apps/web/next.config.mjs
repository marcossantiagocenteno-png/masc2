/**
 * Las pruebas E2E usan su propio directorio de compilación (.next-e2e). Así pueden
 * ejecutarse mientras hay un servidor de desarrollo abierto en el mismo proyecto.
 *
 * @type {import('next').NextConfig}
 */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.NOVEL_ENGINE_E2E === "1" ? ".next-e2e" : ".next",
};

export default nextConfig;
