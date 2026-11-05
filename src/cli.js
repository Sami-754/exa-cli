import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { execSync } from "node:child_process";
import readline from "node:readline/promises";
import { fileURLToPath } from "node:url";

import { VERSION } from "./version.js";
import { configDir, configPath, ensureKey, loadKey, mask, saveKey } from "./config.js";
import * as client from "./client.js";

const SEARCH_HELP = `search QUERY [--limit N] [--type TYPE] [--category CAT] [--domain D] [--exclude-domain D]
       [--from ISO] [--to ISO] [--json] [--help]
       [--content MODE] [--max-chars N] [--fresh HOURS] [--snapshot ISO]
       [--schema FILE] [--prompt TEXT]

content modes (pick exactly one):
  highlights (default)   bare highlights:true  — token-efficient excerpts
  text                   contents.text = {maxCharacters} (or true if --max-chars omitted)
  summary                contents.summary = true (per-result LLM synthesis)
  none                   no contents — metadata only

search types (--type):
  auto        default  (balanced)
  lite        low-latency, reduced params (highlights/text/snapshot only)
  deep-lite   lightweight synthesis, ~4s
  deep        multi-step synthesis
  deep-reasoning  strongest research (legacy name)
  fast, instant   legacy (accepted, forwarded as-is)

categories (--category):
  company, people, publication, news, "personal site", "financial report"
  never invent github/documentation/qa/pdf; coding queries use plain search

filters:
  --domain D          includeDomains (repeatable; supports *.example.com, example.com/docs)
  --exclude-domain D  excludeDomains (repeatable)
  --from ISO          startPublishedDate (ISO 8601)
  --to ISO            endPublishedDate
  --fresh HOURS       contents.maxAgeHours  0=always fresh, -1=cache only, positive=cap age
  --snapshot ISO      contents.snapshotAsOf (ISO date-time pin)
  --schema FILE       outputSchema (JSON file; not supported with --type lite)
  --prompt TEXT       systemPrompt (synthesis guidance)
  --limit N           numResults (1-100, default 10)

recommended minimal request (skill guidance):
  { "query": "...", "type": "auto", "contents": { "highlights": true } }
every extra flag must be task-justified.`;

const CONTENTS_HELP = `contents URLS... [--max-chars N] [--json] [--help]
    [--content MODE] [--fresh HOURS] [--snapshot ISO] [--crawl-timeout MS]
    [--subpages N] [--subpage-target TEXT] [--extras-links N] [--extras-images N]

content modes (pick exactly one; top-level on this endpoint, not nested):
  highlights (default)   bare highlights:true
  text                   text:true, or text={maxCharacters} with --max-chars
  summary                summary:true (per-page compression)

modes only:
  --fresh HOURS       maxAgeHours (0=always fresh, -1=cache only)
  --snapshot ISO      snapshotAsOf (top-level ISO date-time pin)
  --crawl-timeout MS  livecrawlTimeout (ms; use when livecrawl matters)
  --subpages N        subpages (crawl linked subpages per result)
  --subpage-target    subpageTarget (string, repeatable)
  --extras-links N    extras.links
  --extras-images N   extras.imageLinks

URLs can come from args or stdin (one per line). Responses may include
'statuses' — HTTP 200 does not mean every URL succeeded.`;

const SIMILAR_HELP = `similar URL [--limit N] [--json]
  DEPRECATED: upstream prefers search with a query derived from the seed page.`;

const ANSWER_HELP = `answer QUERY [--json] [--stream] [--text] [--schema FILE] [--prompt TEXT]
         [--model M] [--country CC]

flags:
  --text         include full text in citations
  --schema FILE  outputSchema (JSON file)
  --prompt TEXT  systemPrompt
  --model M      exa | exa-pro | exa-research | exa-fast
  --country CC   userLocation 2-letter ISO country
  --stream       SSE token streaming (prints chunks as they arrive)
  --json         raw JSON (no stream)

surface: /answer — grounded answer with citations; prefer search when the
app already has its own LLM.`;

const AGENT_HELP = `agent QUERY [--effort E] [--schema FILE] [--prompt TEXT]
      [--data FILE] [--exclusion FILE] [--previous RUNID]
      [--max-cost N] [--max-duration N] [--wait] [--json]

subcommands:
  agent QUERY ...       create a run (POST /agent/runs)
  agent get RUNID       get one run
  agent list [--limit N] [--cursor C]   list runs
  agent cancel RUNID    cancel (POST /agent/runs/{id}/cancel)
  agent stop RUNID      stop (POST /agent/runs/{id}/stop)
  agent events RUNID [--json]  list/replay events (SSE via curl for live)

create flags:
  --effort E       minimal|low|medium|high|xhigh|auto|ultra (default auto)
  --schema FILE    outputSchema (JSON file) — validated structured output
  --prompt TEXT    systemPrompt
  --data FILE      input.data (JSON array file — rows to enrich)
  --exclusion FILE input.exclusion (JSON array — records to avoid)
  --previous ID    previousRunId (follow-up on a completed run)
  --max-cost N     budget.maxCostDollars (auto/ultra only, 1-100)
  --max-duration N budget.maxDurationSeconds (ultra only, 300-10800)
  --wait           poll until terminal status then print
  --json           raw JSON

lifecycle: create → id (agent_run_*) → poll GET until status is
completed|failed|cancelled → only completed carries output.`;

const MONITORS_HELP = `monitors list [--status S] [--name TEXT] [--limit N] [--cursor C]
monitors create --query TEXT --webhook URL [--name N] [--interval P]
                [--limit N] [--domain D] [--exclude-domain D]
                [--json] [--wait]
monitors get ID
monitors update ID (--name N | --pause | --resume) [--query TEXT] [--interval P] [--webhook URL]
monitors delete ID
monitors trigger ID
monitors runs ID [--limit N]
monitors run ID RUNID
monitors batch ACTION --filter ... [--dry-run] [--limit N]

create flags:
  --query TEXT    required search.query
  --webhook URL   required webhook.url (HTTPS; localhost/private rejected)
  --name N        display name
  --interval P    trigger {type:interval, period:"1h"|"1d"|"7d"} (min 1h)
  --limit N       search.numResults
  --domain D      includeDomains (repeatable)

update flags:
  --pause / --resume  status paused|active
  --name, --query, --interval, --webhook, --metadata KEY=VAL (repeatable)
  --no-schedule       trigger=null ("no" schedule)

run control: trigger posts POST /monitors/{id}/trigger; runs GET /monitors/{id}/runs

webhookSecret is returned ONLY at creation — save it immediately.`;

const BATCHES_HELP = `batches COMMAND

  batches create --mode MODE --requests FILE --json
  batches get ID | batches list [--limit N] | batches cancel ID
  --mode search|contents|agent  --requests FILE (JSON array of request objects)

Async batch runs: submit many Exa requests at once, poll status.`;

function printJson(obj) {
  process.stdout.write(JSON.stringify(obj, null, 2) + "\n");
}

function loadJsonFile(filepath) {
  try {
    const raw = fs.readFileSync(filepath, "utf-8");
    return JSON.parse(raw);
  } catch (err) {
    if (err.code === "ENOENT") {
      console.error(`error: file not found: ${filepath}`);
    } else {
      console.error(`error: bad JSON in ${filepath}: ${err.message}`);
    }
    process.exit(2);
  }
}

function parseKVs(items) {
  const d = {};
  for (const it of items) {
    if (!it.includes("=")) {
      console.error(`error: --metadata expects KEY=VALUE, got ${JSON.stringify(it)}`);
      process.exit(2);
    }
    const idx = it.indexOf("=");
    d[it.slice(0, idx)] = it.slice(idx + 1);
  }
  return d;
}

async function readAllStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf-8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => {
      resolve(data);
    });
  });
}

export async function cmdSearch(args) {
  if (args.some((a) => a === "-h" || a === "--help")) {
    console.log(SEARCH_HELP);
    return 0;
  }
  let limit = 10;
  let typ = null;
  let jflag = false;
  let maxChars = 4000;
  let contentMode = "highlights";
  const queryParts = [];
  const domains = [];
  const excludeDomains = [];
  let category = null;
  let start = null;
  let end = null;
  let fresh = null;
  let snapshot = null;
  let schemaFile = null;
  let prompt = null;

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--json") {
      jflag = true;
    } else if ((a === "-n" || a === "--limit") && i + 1 < args.length) {
      limit = parseInt(args[++i], 10);
    } else if (a === "--type" && i + 1 < args.length) {
      typ = args[++i];
    } else if (a === "--max-chars" && i + 1 < args.length) {
      maxChars = parseInt(args[++i], 10);
    } else if (a === "--content" && i + 1 < args.length) {
      const m = args[++i].toLowerCase();
      if (!["highlights", "text", "summary", "none"].includes(m)) {
        console.error(`error: --content must be highlights|text|summary|none, got ${JSON.stringify(m)}`);
        return 2;
      }
      contentMode = m;
    } else if (a === "--text") {
      contentMode = "text";
    } else if (a === "--summary") {
      contentMode = "summary";
    } else if (a === "--no-text") {
      if (contentMode === "text") contentMode = "highlights";
    } else if (a === "--no-highlights") {
      if (contentMode === "highlights") contentMode = "none";
    } else if (a === "--domain" && i + 1 < args.length) {
      domains.push(args[++i]);
    } else if (a === "--exclude-domain" && i + 1 < args.length) {
      excludeDomains.push(args[++i]);
    } else if (a === "--category" && i + 1 < args.length) {
      category = args[++i];
    } else if (a === "--from" && i + 1 < args.length) {
      start = args[++i];
    } else if (a === "--to" && i + 1 < args.length) {
      end = args[++i];
    } else if (a === "--fresh" && i + 1 < args.length) {
      fresh = parseInt(args[++i], 10);
    } else if (a === "--snapshot" && i + 1 < args.length) {
      snapshot = args[++i];
    } else if (a === "--schema" && i + 1 < args.length) {
      schemaFile = args[++i];
    } else if (a === "--prompt" && i + 1 < args.length) {
      prompt = args[++i];
    } else if (a.startsWith("-")) {
      console.error(`unknown flag: ${a}`);
      return 2;
    } else {
      queryParts.push(a);
    }
  }

  const query = queryParts.join(" ").trim();
  if (!query) {
    console.error("error: search query required");
    return 2;
  }
  if (limit < 1 || limit > 100) {
    console.error("error: --limit must be 1..100");
    return 2;
  }

  const key = await ensureKey();
  const contents = {};
  if (contentMode === "highlights") {
    contents.highlights = true;
  } else if (contentMode === "text") {
    if (maxChars !== 4000) {
      contents.text = { maxCharacters: maxChars };
    } else {
      contents.text = true;
    }
  } else if (contentMode === "summary") {
    contents.summary = true;
  }

  if (fresh !== null && !isNaN(fresh)) {
    contents.maxAgeHours = fresh;
  }
  if (snapshot) {
    contents.snapshotAsOf = snapshot;
  }

  const payload = {
    query,
    numResults: limit,
  };
  if (typ) payload.type = typ;
  if (Object.keys(contents).length > 0) payload.contents = contents;
  if (category) payload.category = category;
  if (domains.length > 0) payload.includeDomains = domains;
  if (excludeDomains.length > 0) payload.excludeDomains = excludeDomains;
  if (start) payload.startPublishedDate = start;
  if (end) payload.endPublishedDate = end;
  if (schemaFile) payload.outputSchema = loadJsonFile(schemaFile);
  if (prompt) payload.systemPrompt = prompt;

  const res = await client.post("/search", payload, key);
  if (jflag) {
    printJson(res);
    return 0;
  }

  const results = (res && Array.isArray(res.results)) ? res.results : [];
  if (results.length === 0) {
    console.error("no results");
    console.log("[]");
    return 0;
  }

  for (const r of results) {
    console.log(`${r.title || ""}\n  ${r.url || ""}\n  ${r.publishedDate || ""}  score=${r.score || ""}`);
    if (contentMode === "highlights") {
      const hl = r.highlights || [];
      if (hl.length > 0) {
        console.log(`  ${String(hl[0]).slice(0, 200)}`);
      }
    } else if (contentMode === "text") {
      const t = r.text || "";
      if (t) {
        console.log(`  ${String(t).slice(0, maxChars)}`);
      }
    } else if (contentMode === "summary") {
      let s = r.summary || "";
      if (Array.isArray(s)) s = s[0] || "";
      console.log(`  ${String(s).slice(0, 500)}`);
    }
    console.log();
  }

  if (res && res.output) {
    console.error("structured output:");
    printJson(res.output);
  }
  return 0;
}

export async function cmdContents(args) {
  if (args.some((a) => a === "-h" || a === "--help")) {
    console.log(CONTENTS_HELP);
    return 0;
  }
  let jflag = false;
  let maxChars = 4000;
  let contentMode = "highlights";
  let fresh = null;
  let snapshot = null;
  let crawlTimeout = null;
  let subpages = null;
  const subpageTargets = [];
  let extrasLinks = null;
  let extrasImages = null;
  const urls = [];

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--json") {
      jflag = true;
    } else if (a === "--max-chars" && i + 1 < args.length) {
      maxChars = parseInt(args[++i], 10);
    } else if (a === "--content" && i + 1 < args.length) {
      const m = args[++i].toLowerCase();
      if (!["highlights", "text", "summary"].includes(m)) {
        console.error(`error: --content must be highlights|text|summary, got ${JSON.stringify(m)}`);
        return 2;
      }
      contentMode = m;
    } else if (a === "--text") {
      contentMode = "text";
    } else if (a === "--summary") {
      contentMode = "summary";
    } else if (a === "--fresh" && i + 1 < args.length) {
      fresh = parseInt(args[++i], 10);
    } else if (a === "--snapshot" && i + 1 < args.length) {
      snapshot = args[++i];
    } else if (a === "--crawl-timeout" && i + 1 < args.length) {
      crawlTimeout = parseInt(args[++i], 10);
    } else if (a === "--subpages" && i + 1 < args.length) {
      subpages = parseInt(args[++i], 10);
    } else if (a === "--subpage-target" && i + 1 < args.length) {
      subpageTargets.push(args[++i]);
    } else if (a === "--extras-links" && i + 1 < args.length) {
      extrasLinks = parseInt(args[++i], 10);
    } else if (a === "--extras-images" && i + 1 < args.length) {
      extrasImages = parseInt(args[++i], 10);
    } else if (a.startsWith("-")) {
      console.error(`unknown flag: ${a}`);
      return 2;
    } else {
      urls.push(a);
    }
  }

  if (urls.length === 0 && !process.stdin.isTTY) {
    const stdinData = await readAllStdin();
    for (const line of stdinData.split("\n")) {
      const s = line.trim();
      if (s) urls.push(s);
    }
  }

  if (urls.length === 0) {
    console.error("error: at least one URL required");
    return 2;
  }

  const key = await ensureKey();
  const payload = { urls };

  if (contentMode === "text") {
    if (maxChars !== 4000) {
      payload.text = { maxCharacters: maxChars };
    } else {
      payload.text = true;
    }
  } else if (contentMode === "summary") {
    payload.summary = true;
  } else {
    payload.highlights = true;
  }

  if (fresh !== null && !isNaN(fresh)) payload.maxAgeHours = fresh;
  if (snapshot) payload.snapshotAsOf = snapshot;
  if (crawlTimeout !== null && !isNaN(crawlTimeout)) payload.livecrawlTimeout = crawlTimeout;
  if (subpages !== null && !isNaN(subpages)) payload.subpages = subpages;
  if (subpageTargets.length > 0) {
    payload.subpageTarget = subpageTargets.length === 1 ? subpageTargets[0] : subpageTargets;
  }
  if (extrasLinks !== null || extrasImages !== null) {
    const extras = {};
    if (extrasLinks !== null) extras.links = extrasLinks;
    if (extrasImages !== null) extras.imageLinks = extrasImages;
    payload.extras = extras;
  }

  const res = await client.post("/contents", payload, key);
  if (jflag) {
    printJson(res);
    return 0;
  }

  const results = (res && Array.isArray(res.results)) ? res.results : [];
  const statuses = {};
  if (res && Array.isArray(res.statuses)) {
    for (const s of res.statuses) {
      if (s && s.id) statuses[s.id] = s.status;
    }
  }

  for (const r of results) {
    console.log(r.url || "");
    const t = r.text || "";
    if (t) console.log(t.slice(0, maxChars));
    const hl = r.highlights || [];
    if (hl.length > 0) {
      for (const h of hl.slice(0, 3)) {
        console.log(String(h).slice(0, 200));
      }
    }
    const s = r.summary;
    if (s) console.log(String(s).slice(0, 500));
    console.log();
  }

  const bad = Object.entries(statuses).filter(([_, v]) => v !== "success");
  if (bad.length > 0) {
    console.error("statuses (errors):");
    for (const [k, v] of bad) {
      console.error(`  ${k}: ${v}`);
    }
  }

  if (results.length === 0) {
    console.error("no results");
  }
  return 0;
}

export async function cmdSimilar(args) {
  if (args.some((a) => a === "-h" || a === "--help")) {
    console.log(SIMILAR_HELP);
    return 0;
  }
  let jflag = false;
  let limit = 10;
  const urls = [];

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--json") {
      jflag = true;
    } else if (a === "--limit" && i + 1 < args.length) {
      limit = parseInt(args[++i], 10);
    } else if (a.startsWith("-")) {
      console.error(`unknown flag: ${a}`);
      return 2;
    } else {
      urls.push(a);
    }
  }

  if (urls.length === 0) {
    console.error("error: similar requires a URL");
    return 2;
  }

  console.error("warning: /findSimilar is deprecated — prefer search with query from the seed page");
  const key = await ensureKey();
  const res = await client.post("/findSimilar", { url: urls[0], numResults: limit }, key);

  if (jflag) {
    printJson(res);
    return 0;
  }

  const results = (res && Array.isArray(res.results)) ? res.results : [];
  for (const r of results) {
    console.log(`${r.title || ""}\n  ${r.url || ""}\n`);
  }
  if (results.length === 0) {
    console.error("no results");
  }
  return 0;
}

export async function cmdAnswer(args) {
  if (args.some((a) => a === "-h" || a === "--help")) {
    console.log(ANSWER_HELP);
    return 0;
  }
  let jflag = false;
  let stream = false;
  let text = false;
  let schemaFile = null;
  let prompt = null;
  let model = null;
  let country = null;
  const q = [];

  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--json") {
      jflag = true;
    } else if (a === "--stream") {
      stream = true;
    } else if (a === "--text") {
      text = true;
    } else if (a === "--schema" && i + 1 < args.length) {
      schemaFile = args[++i];
    } else if (a === "--prompt" && i + 1 < args.length) {
      prompt = args[++i];
    } else if (a === "--model" && i + 1 < args.length) {
      model = args[++i];
    } else if (a === "--country" && i + 1 < args.length) {
      country = args[++i];
    } else if (a.startsWith("-")) {
      console.error(`unknown flag: ${a}`);
      return 2;
    } else {
      q.push(a);
    }
  }

  const query = q.join(" ").trim();
  if (!query) {
    console.error("error: answer query required");
    return 2;
  }

  const key = await ensureKey();
  const payload = { query };
  if (stream) payload.stream = true;
  if (text) payload.text = true;
  if (schemaFile) payload.outputSchema = loadJsonFile(schemaFile);
  if (prompt) payload.systemPrompt = prompt;
  if (model) payload.model = model;
  if (country) payload.userLocation = country;

  const res = await client.post("/answer", payload, key);
  if (jflag) {
    printJson(res);
    return 0;
  }

  if (stream) {
    const raw = (res && res.raw) ? res.raw : "";
    if (raw) {
      console.log(raw);
      return 0;
    }
  }

  const ans = (res && res.answer) ? res.answer : "";
  console.log(ans);

  const cites = (res && Array.isArray(res.citations)) ? res.citations : [];
  if (cites.length > 0) {
    console.error("\nSources:");
    for (const c of cites.slice(0, 5)) {
      if (typeof c === "object" && c !== null) {
        console.error(`  - ${c.url || c.id}: ${c.title || ""}`);
      } else {
        console.error(`  - ${c}`);
      }
    }
  }
  return 0;
}

async function pollRun(runId, key, intervalSec = 4, timeoutSec = 3600) {
  const deadline = Date.now() + timeoutSec * 1000;
  while (true) {
    const run = await client.get(`/agent/runs/${runId}`, key);
    const status = run ? run.status : "unknown";
    console.error(`status=${status}`);
    if (["completed", "failed", "cancelled"].includes(status)) {
      return run;
    }
    if (Date.now() > deadline) {
      console.error("error: poll timeout");
      return run;
    }
    await new Promise((r) => setTimeout(r, intervalSec * 1000));
  }
}

export async function cmdAgent(args) {
  if (args.length === 0 || args.some((a) => a === "-h" || a === "--help")) {
    console.log(AGENT_HELP);
    return args.length === 0 ? 2 : 0;
  }

  const sub = args[0];
  const rest = args.slice(1);

  if (["get", "cancel", "stop", "events"].includes(sub)) {
    if (rest.length === 0) {
      console.error(`error: agent ${sub} requires RUNID`);
      return 2;
    }
    const rid = rest[0];
    const key = await ensureKey();
    if (sub === "get") {
      printJson(await client.get(`/agent/runs/${rid}`, key));
    } else if (sub === "cancel") {
      printJson(await client.post(`/agent/runs/${rid}/cancel`, {}, key));
    } else if (sub === "stop") {
      printJson(await client.post(`/agent/runs/${rid}/stop`, {}, key));
    } else {
      printJson(await client.get(`/agent/runs/${rid}/events`, key));
    }
    return 0;
  }

  if (sub === "list") {
    let limit = 20;
    let cursor = null;
    for (let i = 0; i < rest.length; i++) {
      const a = rest[i];
      if (a === "--limit" && i + 1 < rest.length) {
        limit = parseInt(rest[++i], 10);
      } else if (a === "--cursor" && i + 1 < rest.length) {
        cursor = rest[++i];
      } else if (a === "--json") {
        // ok
      } else if (a.startsWith("-")) {
        console.error(`unknown flag: ${a}`);
        return 2;
      }
    }
    const key = await ensureKey();
    printJson(await client.get("/agent/runs", key, { limit, cursor }));
    return 0;
  }

  const createArgs = sub === "create" ? args.slice(1) : args;
  let effort = "auto";
  let schemaFile = null;
  let prompt = null;
  let dataFile = null;
  let exclusionFile = null;
  let previous = null;
  let maxCost = null;
  let maxDuration = null;
  let wait = false;
  let jflag = false;
  const queryParts = [];

  for (let i = 0; i < createArgs.length; i++) {
    const a = createArgs[i];
    if (a === "--effort" && i + 1 < createArgs.length) {
      effort = createArgs[++i];
    } else if (a === "--schema" && i + 1 < createArgs.length) {
      schemaFile = createArgs[++i];
    } else if (a === "--prompt" && i + 1 < createArgs.length) {
      prompt = createArgs[++i];
    } else if (a === "--data" && i + 1 < createArgs.length) {
      dataFile = createArgs[++i];
    } else if (a === "--exclusion" && i + 1 < createArgs.length) {
      exclusionFile = createArgs[++i];
    } else if (a === "--previous" && i + 1 < createArgs.length) {
      previous = createArgs[++i];
    } else if (a === "--max-cost" && i + 1 < createArgs.length) {
      maxCost = parseFloat(createArgs[++i]);
    } else if (a === "--max-duration" && i + 1 < createArgs.length) {
      maxDuration = parseInt(createArgs[++i], 10);
    } else if (a === "--wait") {
      wait = true;
    } else if (a === "--json") {
      jflag = true;
    } else if (a.startsWith("-")) {
      console.error(`unknown flag: ${a}`);
      return 2;
    } else {
      queryParts.push(a);
    }
  }

  const query = queryParts.join(" ").trim();
  if (!query) {
    console.error("error: agent query required");
    return 2;
  }

  const validEfforts = ["minimal", "low", "medium", "high", "xhigh", "auto", "ultra"];
  if (!validEfforts.includes(effort)) {
    console.error(`error: --effort must be minimal|low|medium|high|xhigh|auto|ultra, got ${JSON.stringify(effort)}`);
    return 2;
  }

  const key = await ensureKey();
  const payload = { query, effort };
  if (schemaFile) payload.outputSchema = loadJsonFile(schemaFile);
  if (prompt) payload.systemPrompt = prompt;

  const inp = {};
  if (dataFile) inp.data = loadJsonFile(dataFile);
  if (exclusionFile) inp.exclusion = loadJsonFile(exclusionFile);
  if (Object.keys(inp).length > 0) payload.input = inp;

  if (previous) payload.previousRunId = previous;

  const budget = {};
  if (maxCost !== null && !isNaN(maxCost)) budget.maxCostDollars = maxCost;
  if (maxDuration !== null && !isNaN(maxDuration)) budget.maxDurationSeconds = maxDuration;
  if (Object.keys(budget).length > 0) payload.budget = budget;

  let run = await client.post("/agent/runs", payload, key);
  const rid = run ? run.id : "";
  if (wait && rid) {
    run = await pollRun(rid, key);
  }

  if (jflag) {
    printJson(run);
  } else {
    console.error(`id=${rid} status=${run ? run.status : ""} stopReason=${run ? run.stopReason : ""}`);
    const out = run ? run.output : null;
    if (out && typeof out === "object") {
      if (out.text) console.log(out.text);
      if (out.structured !== undefined && out.structured !== null) printJson(out.structured);
      if (out.grounding) {
        console.error("\nGrounding:");
        console.error(out.grounding);
      }
    } else if (out) {
      console.log(out);
    }
    const err = run ? run.error : null;
    if (err) {
      console.error(`error: ${err}`);
      return 1;
    }
  }
  return 0;
}

export async function cmdMonitors(args) {
  if (args.length === 0 || args.some((a) => a === "-h" || a === "--help")) {
    console.log(MONITORS_HELP);
    return args.length === 0 ? 2 : 0;
  }

  const sub = args[0];
  const rest = args.slice(1);
  const key = await ensureKey();

  if (sub === "list") {
    let status = null;
    let name = null;
    let limit = 50;
    let cursor = null;
    for (let i = 0; i < rest.length; i++) {
      const a = rest[i];
      if (a === "--status" && i + 1 < rest.length) {
        status = rest[++i];
      } else if (a === "--name" && i + 1 < rest.length) {
        name = rest[++i];
      } else if (a === "--limit" && i + 1 < rest.length) {
        limit = parseInt(rest[++i], 10);
      } else if (a === "--cursor" && i + 1 < rest.length) {
        cursor = rest[++i];
      } else if (a === "--json") {
        // ok
      } else if (a.startsWith("-")) {
        console.error(`unknown flag: ${a}`);
        return 2;
      }
    }
    const res = await client.get("/monitors", key, { status, name, limit, cursor });
    printJson(res);
    return 0;
  }

  if (sub === "get" && rest.length > 0) {
    printJson(await client.get(`/monitors/${rest[0]}`, key));
    return 0;
  }

  if (sub === "delete" && rest.length > 0) {
    printJson(await client.del(`/monitors/${rest[0]}`, key));
    return 0;
  }

  if (sub === "trigger" && rest.length > 0) {
    printJson(await client.post(`/monitors/${rest[0]}/trigger`, {}, key));
    return 0;
  }

  if (sub === "runs" && rest.length > 0) {
    const mid = rest[0];
    let limit = 20;
    let cursor = null;
    for (let i = 1; i < rest.length; i++) {
      const a = rest[i];
      if (a === "--limit" && i + 1 < rest.length) {
        limit = parseInt(rest[++i], 10);
      } else if (a === "--cursor" && i + 1 < rest.length) {
        cursor = rest[++i];
      }
    }
    printJson(await client.get(`/monitors/${mid}/runs`, key, { limit, cursor }));
    return 0;
  }

  if (sub === "run" && rest.length >= 2) {
    printJson(await client.get(`/monitors/${rest[0]}/runs/${rest[1]}`, key));
    return 0;
  }

  if (sub === "update" && rest.length > 0) {
    const mid = rest[0];
    const r = rest.slice(1);
    const payload = {};
    for (let i = 0; i < r.length; i++) {
      const a = r[i];
      if (a === "--name" && i + 1 < r.length) {
        payload.name = r[++i];
      } else if (a === "--query" && i + 1 < r.length) {
        if (!payload.search) payload.search = {};
        payload.search.query = r[++i];
      } else if (a === "--interval" && i + 1 < r.length) {
        payload.trigger = { type: "interval", period: r[++i] };
      } else if (a === "--no-schedule") {
        payload.trigger = null;
      } else if (a === "--pause") {
        payload.status = "paused";
      } else if (a === "--resume") {
        payload.status = "active";
      } else if (a === "--webhook" && i + 1 < r.length) {
        if (!payload.webhook) payload.webhook = {};
        payload.webhook.url = r[++i];
      } else if (a === "--metadata" && i + 1 < r.length) {
        if (!payload.metadata) payload.metadata = {};
        Object.assign(payload.metadata, parseKVs([r[++i]]));
      } else if (a === "--json") {
        // ok
      } else if (a.startsWith("-")) {
        console.error(`unknown flag: ${a}`);
        return 2;
      }
    }
    if (Object.keys(payload).length === 0) {
      console.error("error: monitors update needs a field (e.g. --pause, --name, --query)");
      return 2;
    }
    printJson(await client.patch(`/monitors/${mid}`, payload, key));
    return 0;
  }

  if (sub === "batch") {
    let action = null;
    const filt = {};
    let dryRun = true;
    let limit = 50;

    for (let i = 0; i < rest.length; i++) {
      const a = rest[i];
      if (!action && ["delete", "pause", "unpause"].includes(a)) {
        action = a;
      } else if ((a === "--name" || a === "--status") && i + 1 < rest.length) {
        filt[a.slice(2)] = rest[++i];
      } else if (a === "--dry-run") {
        dryRun = true;
      } else if (a === "--no-dry-run") {
        dryRun = false;
      } else if (a === "--limit" && i + 1 < rest.length) {
        limit = parseInt(rest[++i], 10);
      } else if (a === "--metadata" && i + 1 < rest.length) {
        filt.metadata = parseKVs([rest[++i]]);
      } else if (a.startsWith("-")) {
        console.error(`unknown flag: ${a}`);
        return 2;
      }
    }

    if (!action || Object.keys(filt).length === 0) {
      console.error("error: monitors batch ACTION --name|--status|--metadata required");
      return 2;
    }

    if (dryRun) {
      console.error("dry-run preview (default); add --no-dry-run to apply");
    }
    const res = await client.post(
      "/monitors/batch",
      { action, filter: filt, dry_run: dryRun, limit },
      key
    );
    printJson(res);
    return 0;
  }

  if (sub === "create") {
    let name = null;
    let query = null;
    let webhook = null;
    let interval = null;
    let limit = 10;
    const domains = [];
    const excludeDomains = [];

    for (let i = 0; i < rest.length; i++) {
      const a = rest[i];
      if (a === "--name" && i + 1 < rest.length) {
        name = rest[++i];
      } else if (a === "--query" && i + 1 < rest.length) {
        query = rest[++i];
      } else if (a === "--webhook" && i + 1 < rest.length) {
        webhook = rest[++i];
      } else if (a === "--interval" && i + 1 < rest.length) {
        interval = rest[++i];
      } else if (a === "--limit" && i + 1 < rest.length) {
        limit = parseInt(rest[++i], 10);
      } else if (a === "--domain" && i + 1 < rest.length) {
        domains.push(rest[++i]);
      } else if (a === "--exclude-domain" && i + 1 < rest.length) {
        excludeDomains.push(rest[++i]);
      } else if (a === "--json" || a === "--wait") {
        // ok
      } else if (a.startsWith("-")) {
        console.error(`unknown flag: ${a}`);
        return 2;
      } else {
        if (!query) query = a;
      }
    }

    if (!query || !webhook) {
      console.error("error: monitors create requires --query and --webhook");
      return 2;
    }

    const search = { query, numResults: limit };
    if (domains.length > 0) search.includeDomains = domains;
    if (excludeDomains.length > 0) search.excludeDomains = excludeDomains;

    const payload = { search, webhook: { url: webhook } };
    if (name) payload.name = name;
    if (interval) payload.trigger = { type: "interval", period: interval };

    const res = await client.post("/monitors", payload, key);
    printJson(res);

    const secret = res ? res.webhookSecret : null;
    if (secret) {
      console.error(`\nwebhookSecret (save now, shown once): ${secret}`);
    }
    return 0;
  }

  console.error(`unknown monitors subcommand: ${sub}`);
  return 2;
}

export async function cmdBatches(args) {
  if (args.length === 0 || args.some((a) => a === "-h" || a === "--help")) {
    console.log(BATCHES_HELP);
    return args.length === 0 ? 2 : 0;
  }

  const sub = args[0];
  const rest = args.slice(1);
  const key = await ensureKey();

  if (sub === "create") {
    let mode = null;
    let requestsFile = null;
    for (let i = 0; i < rest.length; i++) {
      const a = rest[i];
      if (a === "--mode" && i + 1 < rest.length) {
        mode = rest[++i];
      } else if (a === "--requests" && i + 1 < rest.length) {
        requestsFile = rest[++i];
      } else if (a === "--json") {
        // ok
      } else if (a.startsWith("-")) {
        console.error(`unknown flag: ${a}`);
        return 2;
      }
    }
    if (!mode || !requestsFile) {
      console.error("error: batches create requires --mode and --requests FILE");
      return 2;
    }
    const payload = { mode, requests: loadJsonFile(requestsFile) };
    printJson(await client.post("/batches", payload, key));
    return 0;
  }

  if (sub === "get" && rest.length > 0) {
    printJson(await client.get(`/batches/${rest[0]}`, key));
    return 0;
  }

  if (sub === "cancel" && rest.length > 0) {
    printJson(await client.post(`/batches/${rest[0]}/cancel`, {}, key));
    return 0;
  }

  if (sub === "list") {
    let limit = 20;
    let cursor = null;
    for (let i = 0; i < rest.length; i++) {
      const a = rest[i];
      if (a === "--limit" && i + 1 < rest.length) {
        limit = parseInt(rest[++i], 10);
      } else if (a === "--cursor" && i + 1 < rest.length) {
        cursor = rest[++i];
      }
    }
    printJson(await client.get("/batches", key, { limit, cursor }));
    return 0;
  }

  console.error(`unknown batches subcommand: ${sub}`);
  return 2;
}

export async function cmdAuth(args) {
  if (args.length === 0 || args.some((a) => a === "-h" || a === "--help")) {
    console.log("usage: exa-cli auth login|status|logout [--key KEY]");
    return args.length === 0 ? 2 : 0;
  }

  const sub = args[0];
  if (sub === "login") {
    let key = "";
    for (let j = 0; j < args.length; j++) {
      if (args[j] === "--key" && j + 1 < args.length) {
        key = args[j + 1];
      }
    }
    if (!key) {
      key = await ensureKey();
      return 0;
    }
    const p = saveKey(key);
    console.error(`saved to ${p}`);
    return 0;
  }

  if (sub === "status") {
    const k = loadKey();
    if (!k) {
      console.error("not logged in (no key found)");
      console.log("no_key");
      return 3;
    }
    console.log(`logged_in key=${mask(k)}`);
    return 0;
  }

  if (sub === "logout") {
    const p = configPath();
    if (fs.existsSync(p)) {
      fs.unlinkSync(p);
    }
    console.error("logged out");
    return 0;
  }

  console.error(`unknown auth subcommand: ${sub}`);
  return 2;
}

export async function cmdConfig(args) {
  if (args.length === 0 || args.some((a) => a === "-h" || a === "--help")) {
    console.log("usage: exa-cli config show");
    return args.length === 0 ? 2 : 0;
  }

  if (args[0] === "show") {
    const k = loadKey();
    console.log(`base_url=${client.BASE} timeout=${client.TIMEOUT / 1000}s retries=${client.RETRIES} key=${k ? mask(k) : "(none)"}`);
    console.log(`config_file=${configPath()}`);
    return 0;
  }

  console.error(`unknown config subcommand: ${args[0]}`);
  return 2;
}

export async function cmdUninstall(args) {
  if (args.some((a) => a === "-h" || a === "--help")) {
    console.log(`uninstall [--yes|-y]
  Completely removes exa-cli, including:
  - Agent skill (~/.agents/skills/exa-cli)
  - Config directory and stored API keys (~/.config/exa-cli)
  - Global CLI binary (via npm, bun, or pnpm)`);
    return 0;
  }

  const assumeYes = args.includes("-y") || args.includes("--yes");
  if (!assumeYes) {
    if (!process.stdin.isTTY) {
      console.error("error: confirmation required in non-interactive environment (use --yes)");
      return 2;
    }
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stderr,
    });
    const ans = (await rl.question("Are you sure you want to completely uninstall exa-cli, config, and skills? [y/N]: ")).trim().toLowerCase();
    rl.close();
    if (ans !== "y" && ans !== "yes") {
      console.log("Uninstallation cancelled.");
      return 0;
    }
  }

  // 1. Remove skill directory
  const skillDir = path.join(os.homedir(), ".agents", "skills", "exa-cli");
  if (fs.existsSync(skillDir)) {
    try {
      fs.rmSync(skillDir, { recursive: true, force: true });
      console.log(`✓ Removed agent skill (${skillDir})`);
    } catch (e) {
      console.error(`warning: could not remove skill dir: ${e.message}`);
    }
  }

  // 2. Remove config directory and keys
  const cfgDir = configDir();
  if (fs.existsSync(cfgDir)) {
    try {
      fs.rmSync(cfgDir, { recursive: true, force: true });
      console.log(`✓ Removed configuration directory (${cfgDir})`);
    } catch (e) {
      console.error(`warning: could not remove config dir: ${e.message}`);
    }
  }

  // 3. Uninstall global package using detected package managers
  console.log("Removing exa-cli binary...");
  for (const cmd of ["npm uninstall -g exa-cli", "bun remove -g exa-cli", "pnpm remove -g exa-cli"]) {
    try {
      execSync(cmd, { stdio: "ignore" });
    } catch {
      // ignore
    }
  }

  const localBin = path.join(os.homedir(), ".local", "bin", "exa-cli");
  if (fs.existsSync(localBin)) {
    try {
      fs.unlinkSync(localBin);
    } catch {
      // ignore
    }
  }

  console.log("✓ exa-cli has been completely uninstalled.");
  return 0;
}

export async function runCLI(argv = process.argv.slice(2)) {
  if (argv.length === 0 || argv[0] === "-h" || argv[0] === "--help" || argv[0] === "help") {
    console.log(`exa-cli — unofficial agent-native CLI for the Exa API

usage: exa-cli <command> [args]

commands:
  search QUERY [--limit N] [--type TYPE] [--json]
  contents URLS... [--max-chars N] [--json]
  similar URL [--limit N] [--json]  (deprecated upstream)
  answer QUERY [--stream] [--json]
  agent QUERY [--effort auto|ultra|...] [--schema FILE] [--wait]
  agent get RUNID | agent list | agent cancel|stop RUNID
  monitors list|create|get ID|update ID|delete ID|trigger ID
  monitors runs ID | monitors run ID RUNID | monitors batch ACTION
  batches create|get ID|list|cancel ID
  auth login|status|logout
  config show
  uninstall [--yes]
  version

run \`exa-cli <command> --help\` for per-command flags`);
    return argv.length === 0 ? 2 : 0;
  }

  const [cmd, ...rest] = argv;
  if (cmd === "version") {
    console.log(`exa-cli ${VERSION}`);
    return 0;
  }
  if (cmd === "search") {
    return await cmdSearch(rest);
  }
  if (cmd === "contents" || cmd === "fetch") {
    return await cmdContents(rest);
  }
  if (cmd === "similar") {
    return await cmdSimilar(rest);
  }
  if (cmd === "answer") {
    return await cmdAnswer(rest);
  }
  if (cmd === "agent") {
    return await cmdAgent(rest);
  }
  if (cmd === "monitors" || cmd === "monitor") {
    return await cmdMonitors(rest);
  }
  if (cmd === "batches" || cmd === "batch") {
    return await cmdBatches(rest);
  }
  if (cmd === "auth") {
    return await cmdAuth(rest);
  }
  if (cmd === "config") {
    return await cmdConfig(rest);
  }
  if (cmd === "uninstall") {
    return await cmdUninstall(rest);
  }

  console.error(`unknown command: ${cmd}`);
  console.error("run `exa-cli --help` for usage");
  return 2;
}
