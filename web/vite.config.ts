import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// base "./" so the built site works from any path (the HF Space serves it from its root).
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
});
