// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import { createInterface } from "node:readline";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

let client;
let session;
let initialized = false;

function reply(value) {
  process.stdout.write(JSON.stringify(value) + "\n");
}

function platformPackage() {
  const arch = process.arch === "x64" ? "x64" : process.arch === "arm64" ? "arm64" : process.arch;
  return `copilot-${process.platform}-${arch}`;
}

const VERIFIED_RUNTIME_VERSIONS = new Set(["1.0.67"]);

function locateRuntime() {
  const candidates = [];
  if (process.env.INFOORGBENCH_COPILOT_RUNTIME) candidates.push(process.env.INFOORGBENCH_COPILOT_RUNTIME);
  try {
    const require = createRequire(import.meta.url);
    const packageRoot = dirname(require.resolve("@github/copilot/package.json"));
    candidates.push(join(packageRoot, "node_modules", "@github", platformPackage()));
  } catch {}
  try {
    const globalRoot = execSync("npm root -g", { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
    candidates.push(join(globalRoot, "@github", "copilot", "node_modules", "@github", platformPackage()));
  } catch {}
  const found = candidates.find(path => existsSync(join(path, process.platform === "win32" ? "copilot.exe" : "copilot"))
    && existsSync(join(path, "copilot-sdk", "index.js")));
  if (!found) throw new Error("runtime_missing");
  return found;
}

function runtimeVersion(runtime) {
  try {
    return JSON.parse(readFileSync(join(runtime, "package.json"), "utf8")).version || null;
  } catch {
    return null;
  }
}

function childEnvironment(tokenEnv) {
  const blocked = new Set(["COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", tokenEnv]);
  const secretName = /(?:_API_KEY|_TOKEN|_SECRET|_PASSWORD|_CREDENTIALS?)$/;
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
    !blocked.has(key) && !key.startsWith("COPILOT_PROVIDER_") && !secretName.test(key)));
  env.COPILOT_ALLOW_GET_PROVIDER_ENDPOINT = "true";
  return env;
}

async function initialize(command) {
  if (initialized) throw new Error("already_initialized");
  const runtime = locateRuntime();
  const version = runtimeVersion(runtime);
  if (!VERIFIED_RUNTIME_VERSIONS.has(version) && process.env.INFOORGBENCH_COPILOT_ALLOW_UNVERIFIED !== "1") {
    throw new Error("runtime_version_mismatch");
  }
  const { CopilotClient } = await import(pathToFileURL(join(runtime, "copilot-sdk", "index.js")));
  const token = process.env[command.tokenEnv];
  client = new CopilotClient({
    cliPath: join(runtime, process.platform === "win32" ? "copilot.exe" : "copilot"),
    workingDirectory: command.workingDirectory,
    logLevel: "none",
    ...(token ? { gitHubToken: token, useLoggedInUser: false } : { useLoggedInUser: true }),
    env: childEnvironment(command.tokenEnv),
  });
  await client.start();
  const auth = await client.getAuthStatus();
  if (!auth?.isAuthenticated) throw new Error("authentication_required");
  session = await client.createSession({
    availableTools: [], tools: [], mcpServers: {}, enableConfigDiscovery: false,
    onPermissionRequest: async () => ({ kind: "denied-interactively-by-user" }),
  });
  initialized = true;
  return version;
}

async function close() {
  try {
    if (session?.destroy) await session.destroy();
    else if (session?.sessionId && client?.deleteSession) await client.deleteSession(session.sessionId);
  } finally {
    if (client) await client.stop().catch(() => {});
  }
}

const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  let command;
  try {
    command = JSON.parse(line);
    if (command.command === "init") {
      const runtimeVersion = await initialize(command);
      reply({ ok: true, runtimeVersion });
    } else if (command.command === "endpoint" && initialized) {
      const endpoint = await session.rpc.provider.getEndpoint({ modelId: command.model });
      reply({ ok: true, endpoint });
    } else if (command.command === "close") {
      await close();
      reply({ ok: true });
      break;
    } else {
      throw new Error("invalid_command");
    }
  } catch (error) {
    const code = ["runtime_missing", "runtime_version_mismatch", "authentication_required", "already_initialized", "invalid_command"]
      .includes(error?.message) ? error.message : "sdk_operation_failed";
    reply({ ok: false, code });
    if (command?.command === "init") break;
  }
}
await close().catch(() => {});
