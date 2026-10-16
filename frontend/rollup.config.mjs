import resolve from "@rollup/plugin-node-resolve";
import terser from "@rollup/plugin-terser";
import typescript from "@rollup/plugin-typescript";

// One ES module, committed into the integration so it installs without a build step.
export default {
  input: "src/woow-serial-panel.ts",
  output: {
    file: "../custom_components/woow_serial/frontend/woow-serial-panel.js",
    format: "es",
    inlineDynamicImports: true,
  },
  plugins: [resolve(), typescript(), terser({ format: { comments: false } })],
};
