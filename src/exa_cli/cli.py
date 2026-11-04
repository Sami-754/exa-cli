import json
import sys

from . import __version__
from .config import config_path, ensure_key, load_key, mask, save_key
from . import client

SHARED = """common flags:
  --json            raw JSON on stdout
  -h, --help        this help

global:
  --json only affects data commands; auth/config always print text"""

SEARCH_HELP = """search QUERY [--limit N] [--type TYPE] [--category CAT] [--domain D] [--exclude-domain D]
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
every extra flag must be task-justified."""


CONTENTS_HELP = """contents URLS... [--max-chars N] [--json] [--help]
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
'statuses' — HTTP 200 does not mean every URL succeeded."""


SIMILAR_HELP = """similar URL [--limit N] [--json]
  DEPRECATED: upstream prefers search with a query derived from the seed page."""


ANSWER_HELP = """answer QUERY [--json] [--stream] [--text] [--schema FILE] [--prompt TEXT]
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
app already has its own LLM."""


AGENT_HELP = """agent QUERY [--effort E] [--schema FILE] [--prompt TEXT]
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
completed|failed|cancelled → only completed carries output."""


MONITORS_HELP = """monitors list [--status S] [--name TEXT] [--limit N] [--cursor C]
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

webhookSecret is returned ONLY at creation — save it immediately."""


BATCHES_HELP = """batches COMMAND

  batches create --mode MODE --requests FILE --json
  batches get ID | batches list [--limit N] | batches cancel ID
  --mode search|contents|agent  --requests FILE (JSON array of request objects)

Async batch runs: submit many Exa requests at once, poll status."""


def _j(obj) -> None:
    print(json.dumps(obj, indent=2))


def _load_json_file(path: str):
    p = Path(path)
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        raise SystemExit(2) from None
    except json.JSONDecodeError as e:
        print(f"error: bad JSON in {path}: {e}", file=sys.stderr)
        raise SystemExit(2) from None


def _parse_kvs(items: list[str]) -> dict:
    d = {}
    for it in items:
        if "=" not in it:
            print(f"error: --metadata expects KEY=VALUE, got {it!r}", file=sys.stderr)
            raise SystemExit(2)
        k, v = it.split("=", 1)
        d[k] = v
    return d


def cmd_search(args: list[str]) -> int:
    if any(a in ("-h", "--help") for a in args):
        print(SEARCH_HELP)
        return 0
    limit = 10
    typ = None
    jflag = False
    max_chars = 4000
    content_mode = "highlights"  # highlights|text|summary|none
    query_parts: list[str] = []
    i = 0
    domains: list[str] = []
    exclude_domains: list[str] = []
    category = None
    start = None
    end = None
    fresh = None
    snapshot = None
    schema_file = None
    prompt = None
    while i < len(args):
        a = args[i]
        if a == "--json":
            jflag = True
        elif a in ("-n", "--limit") and i + 1 < len(args):
            limit = int(args[i + 1]); i += 1
        elif a == "--type" and i + 1 < len(args):
            typ = args[i + 1]; i += 1
        elif a == "--max-chars" and i + 1 < len(args):
            max_chars = int(args[i + 1]); i += 1
        elif a == "--content" and i + 1 < len(args):
            m = args[i + 1].lower(); i += 1
            if m not in ("highlights", "text", "summary", "none"):
                print(f"error: --content must be highlights|text|summary|none, got {m!r}", file=sys.stderr)
                return 2
            content_mode = m
        elif a == "--text":
            content_mode = "text"
        elif a == "--summary":
            content_mode = "summary"
        elif a == "--no-text":
            content_mode = "highlights" if content_mode == "text" else content_mode
        elif a == "--no-highlights":
            if content_mode == "highlights":
                content_mode = "none"
        elif a == "--domain" and i + 1 < len(args):
            domains.append(args[i + 1]); i += 1
        elif a == "--exclude-domain" and i + 1 < len(args):
            exclude_domains.append(args[i + 1]); i += 1
        elif a == "--category" and i + 1 < len(args):
            category = args[i + 1]; i += 1
        elif a == "--from" and i + 1 < len(args):
            start = args[i + 1]; i += 1
        elif a == "--to" and i + 1 < len(args):
            end = args[i + 1]; i += 1
        elif a == "--fresh" and i + 1 < len(args):
            fresh = int(args[i + 1]); i += 1
        elif a == "--snapshot" and i + 1 < len(args):
            snapshot = args[i + 1]; i += 1
        elif a == "--schema" and i + 1 < len(args):
            schema_file = args[i + 1]; i += 1
        elif a == "--prompt" and i + 1 < len(args):
            prompt = args[i + 1]; i += 1
        elif a.startswith("-"):
            print(f"unknown flag: {a}", file=sys.stderr)
            return 2
        else:
            query_parts.append(a)
        i += 1
    query = " ".join(query_parts).strip()
    if not query:
        print("error: search query required", file=sys.stderr)
        return 2
    if not (1 <= limit <= 100):
        print("error: --limit must be 1..100", file=sys.stderr)
        return 2
    key = ensure_key()
    contents: dict = {}
    if content_mode == "highlights":
        contents["highlights"] = True
    elif content_mode == "text":
        # bare true recommended; max_chars only when user asked explicitly differs
        if max_chars != 4000:
            contents["text"] = {"maxCharacters": max_chars}
        else:
            contents["text"] = True
    elif content_mode == "summary":
        contents["summary"] = True
    if fresh is not None:
        contents["maxAgeHours"] = fresh
    if snapshot:
        contents["snapshotAsOf"] = snapshot
    payload: dict = {
        "query": query,
        "numResults": limit,
    }
    if typ:
        payload["type"] = typ
    if contents:
        payload["contents"] = contents
    if category:
        payload["category"] = category
    if domains:
        payload["includeDomains"] = domains
    if exclude_domains:
        payload["excludeDomains"] = exclude_domains
    if start:
        payload["startPublishedDate"] = start
    if end:
        payload["endPublishedDate"] = end
    if schema_file:
        payload["outputSchema"] = _load_json_file(schema_file)
    if prompt:
        payload["systemPrompt"] = prompt
    res = client.post("/search", payload, key)
    if jflag:
        _j(res)
        return 0
    results = res.get("results", []) if isinstance(res, dict) else []
    if not results:
        print("no results", file=sys.stderr)
        print("[]")
        return 0
    for r in results:
        print(f"{r.get('title', '')}\n  {r.get('url', '')}\n"
              f"  {r.get('publishedDate', '')}  score={r.get('score', '')}")
        if content_mode == "highlights":
            hl = r.get("highlights") or []
            if hl:
                print(f"  {hl[0][:200]}")
        elif content_mode == "text":
            t = r.get("text") or ""
            if t:
                print(f"  {t[:max_chars]}")
        elif content_mode == "summary":
            s = r.get("summary") or ""
            if isinstance(s, list):
                s = s[0] if s else ""
            print(f"  {str(s)[:500]}")
        print()
    if "output" in res:
        print("structured output:", file=sys.stderr)
        _j(res["output"])
    return 0


def cmd_contents(args: list[str]) -> int:
    if any(a in ("-h", "--help") for a in args):
        print(CONTENTS_HELP)
        return 0
    jflag = False
    max_chars = 4000
    content_mode = "highlights"
    fresh = None
    snapshot = None
    crawl_timeout = None
    subpages = None
    subpage_targets: list[str] = []
    extras_links = None
    extras_images = None
    urls: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            jflag = True
        elif a == "--max-chars" and i + 1 < len(args):
            max_chars = int(args[i + 1]); i += 1
        elif a == "--content" and i + 1 < len(args):
            m = args[i + 1].lower(); i += 1
            if m not in ("highlights", "text", "summary"):
                print(f"error: --content must be highlights|text|summary, got {m!r}", file=sys.stderr)
                return 2
            content_mode = m
        elif a == "--text":
            content_mode = "text"
        elif a == "--summary":
            content_mode = "summary"
        elif a == "--fresh" and i + 1 < len(args):
            fresh = int(args[i + 1]); i += 1
        elif a == "--snapshot" and i + 1 < len(args):
            snapshot = args[i + 1]; i += 1
        elif a == "--crawl-timeout" and i + 1 < len(args):
            crawl_timeout = int(args[i + 1]); i += 1
        elif a == "--subpages" and i + 1 < len(args):
            subpages = int(args[i + 1]); i += 1
        elif a == "--subpage-target" and i + 1 < len(args):
            subpage_targets.append(args[i + 1]); i += 1
        elif a == "--extras-links" and i + 1 < len(args):
            extras_links = int(args[i + 1]); i += 1
        elif a == "--extras-images" and i + 1 < len(args):
            extras_images = int(args[i + 1]); i += 1
        elif a.startswith("-"):
            print(f"unknown flag: {a}", file=sys.stderr)
            return 2
        else:
            urls.append(a)
        i += 1
    if not urls and not sys.stdin.isatty():
        for line in sys.stdin:
            line = line.strip()
            if line:
                urls.append(line)
    if not urls:
        print("error: at least one URL required", file=sys.stderr)
        return 2
    key = ensure_key()
    payload: dict = {"urls": urls}
    if content_mode == "text":
        if max_chars != 4000:
            payload["text"] = {"maxCharacters": max_chars}
        else:
            payload["text"] = True
    elif content_mode == "summary":
        payload["summary"] = True
    else:
        payload["highlights"] = True
    if fresh is not None:
        payload["maxAgeHours"] = fresh
    if snapshot:
        payload["snapshotAsOf"] = snapshot
    if crawl_timeout is not None:
        payload["livecrawlTimeout"] = crawl_timeout
    if subpages is not None:
        payload["subpages"] = subpages
    if subpage_targets:
        payload["subpageTarget"] = subpage_targets[0] if len(subpage_targets) == 1 else subpage_targets
    if extras_links is not None or extras_images is not None:
        extras: dict = {}
        if extras_links is not None:
            extras["links"] = extras_links
        if extras_images is not None:
            extras["imageLinks"] = extras_images
        payload["extras"] = extras
    res = client.post("/contents", payload, key)
    if jflag:
        _j(res)
        return 0
    results = res.get("results", []) if isinstance(res, dict) else []
    statuses = {s.get("id"): s.get("status") for s in (res.get("statuses") or []) if isinstance(s, dict)}
    for r in results:
        print(f"{r.get('url', '')}")
        t = (r.get("text") or "")
        if t:
            print(t[:max_chars])
        hl = r.get("highlights") or []
        if hl:
            for h in hl[:3]:
                print(h[:200])
        s = r.get("summary")
        if s:
            print(str(s)[:500])
        print()
    if statuses:
        bad = {k: v for k, v in statuses.items() if v != "success"}
        if bad:
            print("statuses (errors):", file=sys.stderr)
            for k, v in bad.items():
                print(f"  {k}: {v}", file=sys.stderr)
    if not results:
        print("no results", file=sys.stderr)
    return 0


def cmd_similar(args: list[str]) -> int:
    if any(a in ("-h", "--help") for a in args):
        print(SIMILAR_HELP)
        return 0
    jflag = False
    limit = 10
    urls: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            jflag = True
        elif a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1]); i += 1
        elif a.startswith("-"):
            print(f"unknown flag: {a}", file=sys.stderr)
            return 2
        else:
            urls.append(a)
        i += 1
    if not urls:
        print("error: similar requires a URL", file=sys.stderr)
        return 2
    print("warning: /findSimilar is deprecated — prefer search with query from the seed page", file=sys.stderr)
    key = ensure_key()
    res = client.post("/findSimilar", {"url": urls[0], "numResults": limit}, key)
    if jflag:
        _j(res)
        return 0
    for r in res.get("results", []):
        print(f"{r.get('title', '')}\n  {r.get('url', '')}\n")
    if not res.get("results"):
        print("no results", file=sys.stderr)
    return 0


def cmd_answer(args: list[str]) -> int:
    if any(a in ("-h", "--help") for a in args):
        print(ANSWER_HELP)
        return 0
    jflag = False
    stream = False
    text = False
    schema_file = None
    prompt = None
    model = None
    country = None
    q: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            jflag = True
        elif a == "--stream":
            stream = True
        elif a == "--text":
            text = True
        elif a == "--schema" and i + 1 < len(args):
            schema_file = args[i + 1]; i += 1
        elif a == "--prompt" and i + 1 < len(args):
            prompt = args[i + 1]; i += 1
        elif a == "--model" and i + 1 < len(args):
            model = args[i + 1]; i += 1
        elif a == "--country" and i + 1 < len(args):
            country = args[i + 1]; i += 1
        elif a.startswith("-"):
            print(f"unknown flag: {a}", file=sys.stderr)
            return 2
        else:
            q.append(a)
        i += 1
    query = " ".join(q).strip()
    if not query:
        print("error: answer query required", file=sys.stderr)
        return 2
    key = ensure_key()
    payload: dict = {"query": query}
    if stream:
        payload["stream"] = True
    if text:
        payload["text"] = True
    if schema_file:
        payload["outputSchema"] = _load_json_file(schema_file)
    if prompt:
        payload["systemPrompt"] = prompt
    if model:
        payload["model"] = model
    if country:
        payload["userLocation"] = country
    res = client.post("/answer", payload, key)
    if jflag:
        _j(res)
        return 0
    if stream:
        # raw SSE arrived as text — print verbatim
        raw = res.get("raw") if isinstance(res, dict) else ""
        if raw:
            print(raw)
            return 0
    ans = res.get("answer", "") if isinstance(res, dict) else ""
    print(ans)
    cites = res.get("citations") or []
    if cites:
        print("\nSources:", file=sys.stderr)
        for c in cites[:5]:
            if isinstance(c, dict):
                print(f"  - {c.get('url') or c.get('id')}: {c.get('title', '')}", file=sys.stderr)
            else:
                print(f"  - {c}", file=sys.stderr)
    return 0


def _poll_run(run_id: str, key: str, interval: int = 4, timeout_s: int = 3600) -> dict:
    import time
    deadline = time.time() + timeout_s
    while True:
        run = client.get(f"/agent/runs/{run_id}", key)
        status = run.get("status")
        print(f"status={status}", file=sys.stderr)
        if status in ("completed", "failed", "cancelled"):
            return run
        if time.time() > deadline:
            print("error: poll timeout", file=sys.stderr)
            return run
        time.sleep(interval)


def cmd_agent(args: list[str]) -> int:
    if not args or any(a in ("-h", "--help") for a in args):
        print(AGENT_HELP)
        return 0 if args else 2
    sub = args[0]
    rest = args[1:]
    # subcommands first, otherwise treat whole args as create query
    if sub in ("get", "cancel", "stop", "events"):
        if not rest:
            print(f"error: agent {sub} requires RUNID", file=sys.stderr)
            return 2
        rid = rest[0]
        key = ensure_key()
        if sub == "get":
            _j(client.get(f"/agent/runs/{rid}", key))
        elif sub == "cancel":
            _j(client.post(f"/agent/runs/{rid}/cancel", {}, key))
        elif sub == "stop":
            _j(client.post(f"/agent/runs/{rid}/stop", {}, key))
        else:
            _j(client.get(f"/agent/runs/{rid}/events", key))
        return 0
    if sub == "list":
        limit = 20
        cursor = None
        i = 0
        while i < len(rest):
            a = rest[i]
            if a == "--limit" and i + 1 < len(rest):
                limit = int(rest[i + 1]); i += 1
            elif a == "--cursor" and i + 1 < len(rest):
                cursor = rest[i + 1]; i += 1
            elif a == "--json":
                pass
            elif a.startswith("-"):
                print(f"unknown flag: {a}", file=sys.stderr)
                return 2
            i += 1
        key = ensure_key()
        _j(client.get("/agent/runs", key, {"limit": limit, "cursor": cursor}))
        return 0
    # create: args are the full query + flags (sub == "create" also works)
    if sub == "create":
        rest = args[1:]
    else:
        rest = args
    effort = "auto"
    schema_file = None
    prompt = None
    data_file = None
    exclusion_file = None
    previous = None
    max_cost = None
    max_duration = None
    wait = False
    jflag = False
    query_parts: list[str] = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--effort" and i + 1 < len(rest):
            effort = rest[i + 1]; i += 1
        elif a == "--schema" and i + 1 < len(rest):
            schema_file = rest[i + 1]; i += 1
        elif a == "--prompt" and i + 1 < len(rest):
            prompt = rest[i + 1]; i += 1
        elif a == "--data" and i + 1 < len(rest):
            data_file = rest[i + 1]; i += 1
        elif a == "--exclusion" and i + 1 < len(rest):
            exclusion_file = rest[i + 1]; i += 1
        elif a == "--previous" and i + 1 < len(rest):
            previous = rest[i + 1]; i += 1
        elif a == "--max-cost" and i + 1 < len(rest):
            max_cost = float(rest[i + 1]); i += 1
        elif a == "--max-duration" and i + 1 < len(rest):
            max_duration = int(rest[i + 1]); i += 1
        elif a == "--wait":
            wait = True
        elif a == "--json":
            jflag = True
        elif a.startswith("-"):
            print(f"unknown flag: {a}", file=sys.stderr)
            return 2
        else:
            query_parts.append(a)
        i += 1
    query = " ".join(query_parts).strip()
    if not query:
        print("error: agent query required", file=sys.stderr)
        return 2
    if effort not in ("minimal", "low", "medium", "high", "xhigh", "auto", "ultra"):
        print(f"error: --effort must be minimal|low|medium|high|xhigh|auto|ultra, got {effort!r}", file=sys.stderr)
        return 2
    key = ensure_key()
    payload: dict = {"query": query, "effort": effort}
    if schema_file:
        payload["outputSchema"] = _load_json_file(schema_file)
    if prompt:
        payload["systemPrompt"] = prompt
    inp: dict = {}
    if data_file:
        inp["data"] = _load_json_file(data_file)
    if exclusion_file:
        inp["exclusion"] = _load_json_file(exclusion_file)
    if inp:
        payload["input"] = inp
    if previous:
        payload["previousRunId"] = previous
    budget: dict = {}
    if max_cost is not None:
        budget["maxCostDollars"] = max_cost
    if max_duration is not None:
        budget["maxDurationSeconds"] = max_duration
    if budget:
        payload["budget"] = budget
    run = client.post("/agent/runs", payload, key)
    rid = run.get("id", "")
    if wait and rid:
        run = _poll_run(rid, key)
    if jflag:
        _j(run)
    else:
        print(f"id={rid} status={run.get('status')} stopReason={run.get('stopReason')}", file=sys.stderr)
        out = run.get("output") or {}
        if isinstance(out, dict):
            if out.get("text"):
                print(out["text"])
            if out.get("structured") is not None:
                _j(out["structured"])
            if out.get("grounding"):
                print("\nGrounding:", file=sys.stderr)
                print(out["grounding"], file=sys.stderr)
        else:
            print(out)
        err = run.get("error")
        if err:
            print(f"error: {err}", file=sys.stderr)
            return 1
    return 0


def cmd_monitors(args: list[str]) -> int:
    if not args or any(a in ("-h", "--help") for a in args):
        print(MONITORS_HELP)
        return 0 if args else 2
    sub = args[0]
    rest = args[1:]
    key = ensure_key()
    if sub == "list":
        status = None
        name = None
        limit = 50
        cursor = None
        i = 0
        jflag = False
        while i < len(rest):
            a = rest[i]
            if a == "--status" and i + 1 < len(rest):
                status = rest[i + 1]; i += 1
            elif a == "--name" and i + 1 < len(rest):
                name = rest[i + 1]; i += 1
            elif a == "--limit" and i + 1 < len(rest):
                limit = int(rest[i + 1]); i += 1
            elif a == "--cursor" and i + 1 < len(rest):
                cursor = rest[i + 1]; i += 1
            elif a == "--json":
                jflag = True
            elif a.startswith("-"):
                print(f"unknown flag: {a}", file=sys.stderr)
                return 2
            i += 1
        res = client.get("/monitors", key, {"status": status, "name": name, "limit": limit, "cursor": cursor})
        _j(res)
        return 0
    if sub == "get" and rest:
        _j(client.get(f"/monitors/{rest[0]}", key))
        return 0
    if sub == "delete" and rest:
        _j(client.delete(f"/monitors/{rest[0]}", key))
        return 0
    if sub == "trigger" and rest:
        _j(client.post(f"/monitors/{rest[0]}/trigger", {}, key))
        return 0
    if sub == "runs" and rest:
        mid = rest[0]
        limit = 20
        cursor = None
        i = 1
        while i < len(rest):
            a = rest[i]
            if a == "--limit" and i + 1 < len(rest):
                limit = int(rest[i + 1]); i += 1
            elif a == "--cursor" and i + 1 < len(rest):
                cursor = rest[i + 1]; i += 1
            i += 1
        _j(client.get(f"/monitors/{mid}/runs", key, {"limit": limit, "cursor": cursor}))
        return 0
    if sub == "run" and len(rest) >= 2:
        _j(client.get(f"/monitors/{rest[0]}/runs/{rest[1]}", key))
        return 0
    if sub == "update" and rest:
        mid = rest[0]
        r = rest[1:]
        payload: dict = {}
        i = 0
        while i < len(r):
            a = r[i]
            if a == "--name" and i + 1 < len(r):
                payload["name"] = r[i + 1]; i += 1
            elif a == "--query" and i + 1 < len(r):
                payload.setdefault("search", {})["query"] = r[i + 1]; i += 1
            elif a == "--interval" and i + 1 < len(r):
                payload["trigger"] = {"type": "interval", "period": r[i + 1]}; i += 1
            elif a == "--no-schedule":
                payload["trigger"] = None
            elif a == "--pause":
                payload["status"] = "paused"
            elif a == "--resume":
                payload["status"] = "active"
            elif a == "--webhook" and i + 1 < len(r):
                payload.setdefault("webhook", {})["url"] = r[i + 1]; i += 1
            elif a == "--metadata" and i + 1 < len(r):
                if "metadata" not in payload:
                    payload["metadata"] = {}
                payload["metadata"].update(_parse_kvs([r[i + 1]])); i += 1
            elif a == "--json":
                pass
            elif a.startswith("-"):
                print(f"unknown flag: {a}", file=sys.stderr)
                return 2
            i += 1
        if not payload:
            print("error: monitors update needs a field (e.g. --pause, --name, --query)", file=sys.stderr)
            return 2
        _j(client.patch(f"/monitors/{mid}", payload, key))
        return 0
    if sub == "batch":
        action = None
        filt: dict = {}
        dry_run = True
        limit = 50
        i = 0
        while i < len(rest):
            a = rest[i]
            if action is None and a in ("delete", "pause", "unpause"):
                action = a
            elif a in ("--name", "--status") and i + 1 < len(rest):
                filt[a[2:]] = rest[i + 1]; i += 1
            elif a == "--dry-run":
                dry_run = True
            elif a == "--no-dry-run":
                dry_run = False
            elif a == "--limit" and i + 1 < len(rest):
                limit = int(rest[i + 1]); i += 1
            elif a == "--metadata" and i + 1 < len(rest):
                filt["metadata"] = _parse_kvs([rest[i + 1]]); i += 1
            elif a.startswith("-"):
                print(f"unknown flag: {a}", file=sys.stderr)
                return 2
            i += 1
        if not action or not filt:
            print("error: monitors batch ACTION --name|--status|--metadata required", file=sys.stderr)
            return 2
        if dry_run:
            print("dry-run preview (default); add --no-dry-run to apply", file=sys.stderr)
        res = client.post("/monitors/batch", {"action": action, "filter": filt, "dry_run": dry_run, "limit": limit}, key)
        _j(res)
        return 0
    if sub == "create":
        name = None
        query = None
        webhook = None
        interval = None
        limit = 10
        domains: list[str] = []
        exclude_domains: list[str] = []
        i = 0
        jflag = False
        while i < len(rest):
            a = rest[i]
            if a == "--name" and i + 1 < len(rest):
                name = rest[i + 1]; i += 1
            elif a == "--query" and i + 1 < len(rest):
                query = rest[i + 1]; i += 1
            elif a == "--webhook" and i + 1 < len(rest):
                webhook = rest[i + 1]; i += 1
            elif a == "--interval" and i + 1 < len(rest):
                interval = rest[i + 1]; i += 1
            elif a == "--limit" and i + 1 < len(rest):
                limit = int(rest[i + 1]); i += 1
            elif a == "--domain" and i + 1 < len(rest):
                domains.append(rest[i + 1]); i += 1
            elif a == "--exclude-domain" and i + 1 < len(rest):
                exclude_domains.append(rest[i + 1]); i += 1
            elif a == "--json":
                jflag = True
            elif a == "--wait":
                pass
            elif a.startswith("-"):
                print(f"unknown flag: {a}", file=sys.stderr)
                return 2
            else:
                if query is None:
                    query = a
            i += 1
        if not query or not webhook:
            print("error: monitors create requires --query and --webhook", file=sys.stderr)
            return 2
        search: dict = {"query": query, "numResults": limit}
        if domains:
            search["includeDomains"] = domains
        if exclude_domains:
            search["excludeDomains"] = exclude_domains
        payload: dict = {"search": search, "webhook": {"url": webhook}}
        if name:
            payload["name"] = name
        if interval:
            payload["trigger"] = {"type": "interval", "period": interval}
        res = client.post("/monitors", payload, key)
        _j(res)
        secret = res.get("webhookSecret")
        if secret:
            print(f"\nwebhookSecret (save now, shown once): {secret}", file=sys.stderr)
        return 0
    print(f"unknown monitors subcommand: {sub}", file=sys.stderr)
    return 2


def cmd_batches(args: list[str]) -> int:
    if not args or any(a in ("-h", "--help") for a in args):
        print(BATCHES_HELP)
        return 0 if args else 2
    sub = args[0]
    rest = args[1:]
    key = ensure_key()
    if sub == "create":
        mode = None
        requests_file = None
        i = 0
        jflag = False
        while i < len(rest):
            a = rest[i]
            if a == "--mode" and i + 1 < len(rest):
                mode = rest[i + 1]; i += 1
            elif a == "--requests" and i + 1 < len(rest):
                requests_file = rest[i + 1]; i += 1
            elif a == "--json":
                jflag = True
            elif a.startswith("-"):
                print(f"unknown flag: {a}", file=sys.stderr)
                return 2
            i += 1
        if not mode or not requests_file:
            print("error: batches create requires --mode and --requests FILE", file=sys.stderr)
            return 2
        payload = {"mode": mode, "requests": _load_json_file(requests_file)}
        _j(client.post("/batches", payload, key))
        return 0
    if sub == "get" and rest:
        _j(client.get(f"/batches/{rest[0]}", key))
        return 0
    if sub == "cancel" and rest:
        _j(client.post(f"/batches/{rest[0]}/cancel", {}, key))
        return 0
    if sub == "list":
        limit = 20
        cursor = None
        i = 0
        while i < len(rest):
            a = rest[i]
            if a == "--limit" and i + 1 < len(rest):
                limit = int(rest[i + 1]); i += 1
            elif a == "--cursor" and i + 1 < len(rest):
                cursor = rest[i + 1]; i += 1
            i += 1
        _j(client.get("/batches", key, {"limit": limit, "cursor": cursor}))
        return 0
    print(f"unknown batches subcommand: {sub}", file=sys.stderr)
    return 2


def cmd_auth(args: list[str]) -> int:
    if not args or any(a in ("-h", "--help") for a in args):
        print("usage: exa-cli auth login|status|logout [--key KEY]")
        return 0 if args else 2
    sub = args[0]
    if sub == "login":
        key = ""
        for j, a in enumerate(args):
            if a == "--key" and j + 1 < len(args):
                key = args[j + 1]
        if not key:
            # hidden-ish prompt: avoid echoing via terminal is complex; keep simple
            key = input("Paste your Exa API key: ").strip()
        if not key:
            print("error: empty key", file=sys.stderr)
            return 3
        p = save_key(key)
        print(f"saved to {p}", file=sys.stderr)
        return 0
    if sub == "status":
        k = load_key()
        if not k:
            print("not logged in (no key found)", file=sys.stderr)
            print("no_key")
            return 3
        print(f"logged_in key={mask(k)}")
        return 0
    if sub == "logout":
        p = config_path()
        if p.exists():
            p.unlink()
        print("logged out", file=sys.stderr)
        return 0
    print(f"unknown auth subcommand: {sub}", file=sys.stderr)
    return 2


def cmd_config(args: list[str]) -> int:
    if not args or any(a in ("-h", "--help") for a in args):
        print("usage: exa-cli config show")
        return 0 if args else 2
    if args[0] == "show":
        k = load_key()
        print(f"base_url={client.BASE} timeout={client.TIMEOUT}s "
              f"retries={client.RETRIES} key={mask(k) if k else '(none)'}")
        print(f"config_file={config_path()}")
        return 0
    print(f"unknown config subcommand: {args[0]}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(
            "exa-cli — agent-native CLI for the Exa API\n"
            "\n"
            "usage: exa-cli <command> [args]\n"
            "\n"
            "commands:\n"
            "  search QUERY [--limit N] [--type TYPE] [--json]\n"
            "  contents URLS... [--max-chars N] [--json]\n"
            "  similar URL [--limit N] [--json]  (deprecated upstream)\n"
            "  answer QUERY [--stream] [--json]\n"
            "  agent QUERY [--effort auto|ultra|...] [--schema FILE] [--wait]\n"
            "  agent get RUNID | agent list | agent cancel|stop RUNID\n"
            "  monitors list|create|get ID|update ID|delete ID|trigger ID\n"
            "  monitors runs ID | monitors run ID RUNID | monitors batch ACTION\n"
            "  batches create|get ID|list|cancel ID\n"
            "  auth login|status|logout\n"
            "  config show\n"
            "  version\n"
            "\n"
            "run `exa-cli <command> --help` for per-command flags"
        )
        return 0 if args else 2
    cmd, rest = args[0], args[1:]
    if cmd == "version":
        print(f"exa-cli {__version__}")
        return 0
    if cmd == "search":
        return cmd_search(rest)
    if cmd in ("contents", "fetch"):
        return cmd_contents(rest)
    if cmd == "similar":
        return cmd_similar(rest)
    if cmd == "answer":
        return cmd_answer(rest)
    if cmd == "agent":
        return cmd_agent(rest)
    if cmd in ("monitors", "monitor"):
        return cmd_monitors(rest)
    if cmd in ("batches", "batch"):
        return cmd_batches(rest)
    if cmd == "auth":
        return cmd_auth(rest)
    if cmd == "config":
        return cmd_config(rest)
    print(f"unknown command: {cmd}", file=sys.stderr)
    print("run `exa-cli --help` for usage", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
