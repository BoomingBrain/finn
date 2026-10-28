import { createReadStream, existsSync, statSync } from "node:fs";
import { resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, type Plugin } from "vite";

const SNAPSHOT = fileURLToPath(new URL("../data/snapshot", import.meta.url));

/** Dev only: serve data/snapshot under /data, where the deploy script puts it on the Space. */
function serveSnapshot(): Plugin {
  return {
    name: "serve-snapshot",
    configureServer(server) {
      server.middlewares.use("/data", (req, res, next) => {
        const file = resolve(SNAPSHOT, "." + decodeURIComponent((req.url ?? "/").split("?")[0]));
        if (!file.startsWith(SNAPSHOT + sep) || !existsSync(file) || !statSync(file).isFile()) return next();
        res.setHeader("Content-Type", "application/json");
        createReadStream(file).pipe(res);
      });
    },
  };
}

// base "./" so the built site works from any path (the HF Space serves it from its root).
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss(), serveSnapshot()],
});
