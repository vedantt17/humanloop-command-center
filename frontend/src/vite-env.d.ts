/// <reference types="vite/client" />

declare module "vanta/dist/vanta.topology.min" {
  const effect: (options: Record<string, unknown>) => { destroy: () => void };
  export default effect;
}

