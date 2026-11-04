import json
import sys
from pathlib import Path

from . import __version__
from .config import config_path, ensure_key, load_key, mask, save_key
from . import client


def _j(obj) -> None:
    print(json.dumps(obj, indent=2))


def cmd_search(args: list[str]) -> int:
    if any(a in ("-h", "--help") for a in args):
        print('usage: exa-cli search QUERY [--limit N] [--json] [--type TYPE] '
              '[--category CAT] [--domain D] [--max-chars N] [--fresh HOURS]')
        return 0
    limit = 10
    typ = None
    jflag = False
    max_chars = 4000
    text = True
    highlights = True
    summary = False
    query_parts: list[str] = []
    rest = iter(range(len(args)))
    i = 0
    domains: list[str] = []
    exclude_domains: list[str] = []
    category = None
    start = None
    end = None
    fresh = None
    while i < len(args):
        a = args[i]
        if a in ("--json",):
            jflag = True
        elif a in ("-n", "--limit") and i + 1 < len(args):
            limit = int(args[i + 1]); i += 1
        elif a == "--type" and i + 1 < len(args):
            typ = args[i + 1]; i += 1
        elif a == "--max-chars" and i + 1 < len(args):
            max_chars = int(args[i + 1]); i += 1
        elif a == "--no-text":
            text = False
        elif a == "--no-highlights":
            highlights = False
        elif a == "--summary":
            summary = True
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
    payload: dict = {
        "query": query,
        "numResults": limit,
        "contents": {"text": {"maxCharacters": max_chars} if text else False,
                      "highlights": highlights, "summary": summary},
    }
    if typ:
        payload["type"] = typ
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
    if fresh is not None:
        payload["maxAgeHours"] = fresh
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
        highlights_list = r.get("highlights") or []
        if highlights_list:
            print(f"  {highlights_list[0][:200]}")
        print()
    return 0


def cmd_contents(args: list[str]) -> int:
    jflag = False
    max_chars = 4000
    urls: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            jflag = True
        elif a == "--max-chars" and i + 1 < len(args):
            max_chars = int(args[i + 1]); i += 1
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
    res = client.post("/contents", {"urls": urls,
                                    "text": {"maxCharacters": max_chars},
                                    "highlights": True}, key)
    if jflag:
        _j(res)
        return 0
    results = res.get("results", []) if isinstance(res, dict) else []
    for r in results:
        print(f"{r.get('url', '')}")
        t = (r.get("text") or "")
        if t:
            print(t[:max_chars])
        print()
    if not results:
        print("no results", file=sys.stderr)
    return 0


def cmd_similar(args: list[str]) -> int:
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
    jflag = False
    stream = False
    q: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            jflag = True
        elif a == "--stream":
            stream = True
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
    res = client.post("/answer", {"query": query, "stream": stream}, key)
    if jflag:
        _j(res)
        return 0
    ans = res.get("answer", "") if isinstance(res, dict) else ""
    print(ans)
    cites = res.get("citations") or []
    if cites:
        print("\nSources:", file=sys.stderr)
        for c in cites[:5]:
            print(f"  - {c}", file=sys.stderr)
    return 0


def cmd_auth(args: list[str]) -> int:
    if not args:
        print("usage: exa-cli auth login|status|logout", file=sys.stderr)
        return 2
    sub = args[0]
    if sub == "login":
        key = ""
        for j, a in enumerate(args):
            if a == "--key" and j + 1 < len(args):
                key = args[j + 1]
        if not key:
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
    if not args or args[0] == "show":
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
            "  search QUERY [--limit N] [--json] [--type TYPE] [--category CAT]\n"
            "  contents URLS... [--max-chars N] [--json]\n"
            "  similar URL [--limit N] [--json]\n"
            "  answer QUERY [--stream] [--json]\n"
            "  auth login|status|logout\n"
            "  config show\n"
            "  version\n"
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
    if cmd == "auth":
        return cmd_auth(rest)
    if cmd == "config":
        return cmd_config(rest)
    print(f"unknown command: {cmd}", file=sys.stderr)
    print("run `exa-cli --help` for usage", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
