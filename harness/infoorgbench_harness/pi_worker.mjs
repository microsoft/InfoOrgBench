// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import { readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import path from "node:path";

const config = JSON.parse(await readFile(process.argv[2], "utf8"));
const sdk = await import(pathToFileURL(path.join(config.piPackage, "dist", "index.js")).href);
const ai = await import(pathToFileURL(path.join(config.piAiPackage, "dist", "index.js")).href);
function schema(value) {
  const options = Object.fromEntries(Object.entries(value).filter(([key]) =>
    !["type", "properties", "items", "required", "additionalProperties"].includes(key)));
  if (value.type === "object") return ai.Type.Object(
    Object.fromEntries(Object.entries(value.properties).map(([key, child]) => [key, schema(child)])),
    {...options, additionalProperties: false});
  if (value.type === "array") return ai.Type.Array(schema(value.items), options);
  if (value.type === "integer") return ai.Type.Integer(options);
  if (value.type === "string") return ai.Type.String(options);
  throw new Error(`Unsupported capability schema: ${value.type}`);
}
const modelsPath = path.join(config.sandbox, "models.json");
const compat = config.model.api === "anthropic-messages"
  ? {forceAdaptiveThinking: config.model.reasoning, supportsTemperature: false}
  : config.model.api === "openai-completions"
    ? {supportsUsageInStreaming: true, supportsReasoningEffort: config.model.reasoning,
       supportsDeveloperRole: false, supportsStore: false, maxTokensField: "max_tokens"}
    : {supportsDeveloperRole: true};
await writeFile(modelsPath, JSON.stringify({providers: {pilot: {
  baseUrl: config.endpoint, api: config.model.api, apiKey: process.env.INFOORGBENCH_GATEWAY_TOKEN,
  models: [{id: config.model.id, name: config.model.name, reasoning: config.model.reasoning,
    input: ["text"], cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0},
    contextWindow: config.model.contextWindow, maxTokens: config.model.maxTokens, compat}]
}}}));
const modelRuntime = await sdk.ModelRuntime.create({
  authPath: path.join(config.sandbox, "auth.json"), modelsPath,
});
const model = modelRuntime.getModel("pilot", config.model.id);
if (!model) throw new Error("Exact configured model is absent");
const tools = config.tools.map(row => ({
  name: row.name, label: row.name, description: row.description, parameters: schema(row.parameters),
  execute: async (_id, args) => {
    const response = await fetch(`${config.endpoint}/tools/${row.name}`, {
      method: "POST", headers: {"Content-Type": "application/json",
        "Authorization": `Bearer ${process.env.INFOORGBENCH_GATEWAY_TOKEN}`}, body: JSON.stringify(args),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(result));
    return {content: [{type: "text", text: result.text}], details: {}};
  },
}));
const resourceLoader = {
  getExtensions: () => ({extensions: [], errors: [], runtime: sdk.createExtensionRuntime()}),
  getSkills: () => ({skills: [], diagnostics: []}), getPrompts: () => ({prompts: [], diagnostics: []}),
  getThemes: () => ({themes: [], diagnostics: []}), getAgentsFiles: () => ({agentsFiles: []}),
  getSystemPrompt: () => undefined, getSystemPromptSource: () => undefined,
  getAppendSystemPrompt: () => [config.adapter], getAppendSystemPromptSources: () => [],
  extendResources: () => {}, reload: async () => {},
};
const providerTimeoutMs = config.requestTimeoutMs ?? (config.transport
  ? (config.transport.idle_seconds + config.transport.active_seconds) *
    (config.transport.idle_retries + 1) * 1000 + 30000
  : 150000);
if (!Number.isFinite(providerTimeoutMs) || providerTimeoutMs <= 0) {
  throw new Error("Invalid stream-aware native timeout");
}
if (config.transport || config.requestTimeoutMs) {
  const {configureHttpDispatcher} = await import(pathToFileURL(
    path.join(config.piPackage, "dist", "core", "http-dispatcher.js")).href);
  configureHttpDispatcher(providerTimeoutMs);
}
const settingsManager = sdk.SettingsManager.inMemory({
  ...(config.transport || config.requestTimeoutMs ? {httpIdleTimeoutMs: providerTimeoutMs} : {}),
  compaction: {enabled: false}, retry: {enabled: false, provider: {maxRetries: 0, timeoutMs: providerTimeoutMs}},
  cacheWarming: "off", defaultTools: tools.map(row => row.name),
});
const {session} = await sdk.createAgentSession({
  cwd: config.workspace, agentDir: config.sandbox, modelRuntime, model,
  thinkingLevel: config.model.reasoning ? "medium" : "off",
  resourceLoader, customTools: tools, tools: tools.map(row => row.name),
  sessionManager: sdk.SessionManager.inMemory(config.workspace), settingsManager,
});
try {
  if (JSON.stringify(session.getActiveToolNames().toSorted()) !==
      JSON.stringify(tools.map(row => row.name).toSorted())) throw new Error("Unexpected tool capability");
  await session.prompt(config.prompt);
  const last = session.messages.filter(message => message.role === "assistant").at(-1);
  const result = {
    final: session.getLastAssistantText(),
    completed: !!last && !["error", "aborted"].includes(last.stopReason),
    stopReason: last?.stopReason ?? null, error: last?.errorMessage ?? null,
  };
  await writeFile(config.result, JSON.stringify(result));
  if (!result.completed) process.exitCode = 1;
} finally {
  session.dispose();
}
