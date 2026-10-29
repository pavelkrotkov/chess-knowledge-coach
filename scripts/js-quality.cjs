const fs = require("node:fs");
const path = require("node:path");
const { Linter } = require("eslint");
const escomplex = require("typhonjs-escomplex");

function filesIn(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const name = path.join(directory, entry.name);
    if (entry.isDirectory()) return filesIn(name);
    return /\.(?:js|cjs|mjs)$/.test(name) ? [name] : [];
  });
}

function checkFile(filename) {
  const source = fs.readFileSync(filename, "utf8");
  const report = escomplex.analyzeModule(source, { newmi: true });
  const messages = new Linter().verify(source, [{
    languageOptions: { ecmaVersion: 2020, sourceType: "commonjs" },
    rules: { complexity: ["error", 8] },
  }], filename);
  console.log(`${filename}: MI ${report.maintainability.toFixed(2)}`);
  for (const message of messages) {
    console.error(`${filename}:${message.line}: ${message.message}`);
  }
  return messages.length === 0 && report.maintainability > 50;
}

function main() {
  const files = ["src", "scripts"].flatMap(filesIn).sort();
  if (!files.includes("src/chess_coach/static/board.js")) {
    throw new Error("Required board script is missing");
  }
  const results = files.map(checkFile);
  if (results.some((passed) => !passed)) process.exitCode = 1;
}
main();
