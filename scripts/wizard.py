#!/usr/bin/env python3
"""
scripts/wizard.py — Interactive CLI Setup Wizard for UnifyRouter.

Guides the user through:
  1. Selecting a provider to onboard
  2. Adding API credentials for that provider
  3. Selecting models to enable
  4. Optionally onboarding more providers
  5. Configuring the routing strategy
  6. Configuring the Brain module

The wizard communicates with the running API gateway via HTTP.

Usage:
  ./unifyroute wizard
  # or directly:
  uv run --package shared python scripts/wizard.py
"""
from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).parent.parent

# ── ANSI colour helpers ───────────────────────────────────────────────────────
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"

def bold(t: str) -> str: return _c("1", t)
def green(t: str) -> str: return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def cyan(t: str) -> str: return _c("36", t)
def red(t: str) -> str: return _c("31", t)
def dim(t: str) -> str: return _c("2", t)

def ok(msg: str):   print(f"  {green('✅')} {msg}")
def warn(msg: str): print(f"  {yellow('⚠️')}  {msg}")
def err(msg: str):  print(f"  {red('❌')} {msg}")
def info(msg: str): print(f"  {cyan('ℹ️')}  {msg}")

def hr(char: str = "─", width: int = 64):
    print(dim(char * width))

def banner(title: str):
    print()
    hr("━")
    print(f"  {bold(title)}")
    hr("━")
    print()


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _api_base() -> str:
    base = os.environ.get("API_BASE_URL", "")
    if not base:
        port = os.environ.get("PORT", "6565")
        base = f"http://localhost:{port}"
    return base.rstrip("/")


def _load_env():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "=" in s:
                k, _, v = s.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _get_admin_token() -> Optional[str]:
    """Try to load an admin bearer token from env / well-known files."""
    token = os.environ.get("ADMIN_TOKEN")
    if token:
        return token
    for fname in (".admin_token", ".api_token-raw"):
        p = BASE_DIR / fname
        if p.exists():
            raw = p.read_text().strip()
            if raw:
                return raw
    return None


def _get(path: str, token: str) -> Any:
    import urllib.request
    url = f"{_api_base()}/api{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _post(path: str, body: Any, token: str) -> Any:
    import urllib.request
    url = f"{_api_base()}/api{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


# ── Input helpers ─────────────────────────────────────────────────────────────
def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    display = f"  {prompt}"
    if default:
        display += f" [{dim(default)}]"
    display += ": "
    if secret:
        val = getpass.getpass(display)
    else:
        val = input(display).strip()
    return val or default


def ask_bool(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"  {prompt} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def pick_number(prompt: str, max_n: int) -> int:
    while True:
        raw = input(f"  {prompt}: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= max_n:
            return int(raw)
        warn(f"Enter a number between 1 and {max_n}.")


def pick_numbers_multi(prompt: str, max_n: int, defaults: List[int]) -> List[int]:
    default_str = ",".join(str(d) for d in defaults)
    raw = input(f"  {prompt} [{dim(default_str)}]: ").strip()
    if not raw:
        return defaults
    result = []
    for part in raw.replace(" ", "").split(","):
        try:
            n = int(part)
            if 1 <= n <= max_n:
                result.append(n)
        except ValueError:
            pass
    return result if result else defaults


# ── Wizard steps ──────────────────────────────────────────────────────────────

def step_select_provider(providers: List[Dict]) -> Optional[Dict]:
    """Display provider list and let user pick one. Returns the chosen provider dict."""
    print(f"\n  {'#':<4} {'Name':<28} {'Display Name':<32} {'Type':<10} {'Status'}")
    hr()
    for i, p in enumerate(providers, 1):
        status_txt = green("has creds") if p["has_credentials"] else dim("no creds")
        catalog_txt = cyan(" ⊕catalog") if p["has_catalog"] else ""
        print(
            f"  {i:<4} {p['name']:<28} {p['display_name']:<32} "
            f"{p['auth_type']:<10} {status_txt}{catalog_txt}"
        )
    hr()
    idx = pick_number("Enter provider number to onboard (0 to skip)", len(providers))
    return providers[idx - 1] if idx > 0 else None  # type: ignore[return-value]


def step_add_credentials(provider: Dict) -> List[Dict]:
    """Interactively collect one or more credentials for a provider."""
    credentials = []
    cred_num = 1

    while True:
        print()
        pname = provider["display_name"]
        print(f"  {bold('Credential #' + str(cred_num) + ' for ' + pname)}")
        label = ask("Label", default=provider["name"] + "-key-" + str(cred_num))

        if provider["auth_type"] == "oauth2":
            info(f"OAuth2 provider — credential will be created without a secret key.")
            info("You can complete OAuth by visiting the dashboard after setup.")
            secret = ""
        else:
            secret = ask("API Key / Secret", secret=True)
            if not secret:
                warn("No secret provided — skipping this credential.")
                break

        credentials.append({
            "label": label,
            "secret_key": secret,
            "auth_type": provider["auth_type"],
        })
        ok(f"Credential '{label}' staged.")
        cred_num += 1

        if not ask_bool("Add another credential?", default=False):
            break

    return credentials


def step_select_models(provider: Dict, catalog: List[Dict]) -> List[Dict]:
    """Let user toggle models from the catalog (or manually enter a model ID)."""
    selected_indices: List[int] = []

    if catalog:
        print()
        print(f"  {'#':<4} {'Model ID':<55} {'Tier':<10} {'Cost In/Out per 1k'}")
        hr()
        default_on: List[int] = []
        for i, m in enumerate(catalog, 1):
            cost = f"${m['input_cost_per_1k']:.4f}/${m['output_cost_per_1k']:.4f}"
            tier_c = dim(m["tier"]) if m["tier"] else dim("—")
            print(f"  {i:<4} {m['model_id']:<55} {tier_c:<10} {cost}")
            if m.get("default_enabled"):
                default_on.append(i)
        hr()
        selected_indices = pick_numbers_multi(
            "Toggle model numbers to enable (comma-separated)",
            max_n=len(catalog),
            defaults=default_on,
        )
        selected_models = []
        for idx in selected_indices:
            entry = catalog[idx - 1].copy()
            selected_models.append({
                "model_id": entry["model_id"],
                "display_name": entry["display_name"],
                "tier": entry.get("tier", ""),
                "context_window": entry.get("context_window", 128_000),
                "input_cost_per_1k": entry.get("input_cost_per_1k", 0.0),
                "output_cost_per_1k": entry.get("output_cost_per_1k", 0.0),
                "supports_streaming": entry.get("supports_streaming", True),
                "supports_functions": entry.get("supports_functions", True),
                "enabled": True,
            })
    else:
        info("No pre-built model catalog for this provider.")
        selected_models = []

    # Allow manual addition
    while ask_bool("Add a custom model ID manually?", default=False):
        model_id = ask("Model ID")
        if not model_id:
            continue
        display = ask("Display name", default=model_id)
        tier = ask("Tier (lite / base / thinking / leave blank)", default="")
        selected_models.append({
            "model_id": model_id,
            "display_name": display or model_id,
            "tier": tier,
            "context_window": 128_000,
            "input_cost_per_1k": 0.0,
            "output_cost_per_1k": 0.0,
            "supports_streaming": True,
            "supports_functions": True,
            "enabled": True,
        })
        ok(f"Model '{model_id}' added.")

    return selected_models


def step_routing_strategy(onboarded: List[Dict]) -> Dict:
    """Build routing tier config from onboarded providers/models."""
    print()
    STRATEGIES = ["cheapest_available", "highest_quota", "round_robin"]
    for i, s in enumerate(STRATEGIES, 1):
        print(f"  {i}. {s}")
    strategy_idx = pick_number("Choose default routing strategy", len(STRATEGIES))
    strategy = STRATEGIES[strategy_idx - 1]

    # Collect all selected models across providers for tier assignment
    all_models: List[Dict] = []
    for p in onboarded:
        for m in p["models"]:
            all_models.append({"provider": p["provider_name"], "model_id": m["model_id"], "tier": m["tier"]})

    tiers: Dict[str, Any] = {}
    for tier_name in ("lite", "base", "thinking"):
        tier_models = [m for m in all_models if m["tier"] == tier_name]
        if tier_models:
            tiers[tier_name] = {
                "strategy": strategy,
                "fallback_on": [429, 503, "timeout"],
                "models": [{"provider": m["provider"], "model": m["model_id"]} for m in tier_models],
            }

    # Fall back: auto tier = all models
    if all_models:
        tiers["auto"] = {
            "strategy": strategy,
            "fallback_on": [429, 503, "timeout"],
            "models": [{"provider": m["provider"], "model": m["model_id"]} for m in all_models],
        }

    return tiers


def step_brain_config(onboarded: List[Dict]) -> List[Dict]:
    """Choose a provider/credential/model triple for the brain."""
    brain_entries: List[Dict] = []

    # Build a flat list: [(display, provider_name, cred_label, model_id)]
    candidates: List[tuple] = []
    for p in onboarded:
        for cred in p["credentials"]:
            for m in p["models"]:
                candidates.append((
                    f"{p['provider_name']} / {cred['label']} / {m['model_id']}",
                    p["provider_name"],
                    cred["label"],
                    m["model_id"],
                ))

    if not candidates:
        warn("No provider/credential/model triples found. Skipping brain config.")
        return []

    print()
    for i, (display, *_) in enumerate(candidates, 1):
        print(f"  {i}. {display}")

    idx = pick_number("Select entry for Brain (0 to skip)", len(candidates))
    if idx == 0:
        return []

    _, pname, cred_label, model_id = candidates[idx - 1]
    priority_str = ask("Priority (lower = higher priority)", default="10")
    try:
        priority = int(priority_str)
    except ValueError:
        priority = 10

    brain_entries.append({
        "provider_name": pname,
        "credential_label": cred_label,
        "model_id": model_id,
        "priority": priority,
    })
    ok(f"Brain assigned: {pname} / {cred_label} / {model_id} (priority {priority})")
    return brain_entries


def show_summary(onboarded: List[Dict], routing_tiers: Dict, brain_entries: List[Dict]):
    """Print a summary of everything that will be saved."""
    banner("📋  Summary — Review Before Saving")

    for p in onboarded:
        print(f"  Provider : {bold(p['provider_name'])}")
        for cred in p["credentials"]:
            print(f"    Credential : {cred['label']}")
        for m in p["models"]:
            print(f"    Model      : {m['model_id']} ({m['tier'] or '—'})")
        print()

    if routing_tiers:
        print(f"  Routing Tiers : {', '.join(routing_tiers.keys())}")
    else:
        print("  Routing       : (unchanged)")

    if brain_entries:
        b = brain_entries[0]
        print(f"  Brain         : {b['provider_name']} / {b['credential_label']} / {b['model_id']}")
    else:
        print("  Brain         : (not configured)")


# ── Main wizard entry ─────────────────────────────────────────────────────────

def run_wizard(token: str):
    banner("🧙  LLMWay Setup Wizard")

    # Fetch available providers
    info("Loading provider catalog from gateway...")
    try:
        providers = _get("/admin/wizard/providers/available", token)
    except Exception as e:
        err(f"Could not reach API gateway: {e}")
        err("Make sure UnifyRouter is running:  ./unifyroute start")
        sys.exit(1)

    onboarded: List[Dict] = []

    while True:
        banner(f"Step {len(onboarded) + 1}: Select Provider to Onboard")
        provider = step_select_provider(providers)
        if not provider:
            if not onboarded:
                warn("No providers selected. Exiting wizard.")
                sys.exit(0)
            break

        # Fetch model catalog for this provider
        catalog: List[Dict] = []
        if provider.get("has_catalog"):
            try:
                resp = _get(f"/admin/wizard/models/{provider['name']}", token)
                catalog = resp.get("models", [])
            except Exception:
                warn(f"Could not load model catalog for {provider['name']}.")

        banner(f"Step: Credentials → {provider['display_name']}")
        credentials = step_add_credentials(provider)

        banner(f"Step: Models → {provider['display_name']}")
        models = step_select_models(provider, catalog)

        if not credentials and not models:
            warn("No credentials or models selected. Skipping this provider.")
        else:
            onboarded.append({
                "provider_name": provider["name"],
                "credentials": credentials,
                "models": models,
            })
            ok(f"Provider '{provider['name']}' staged.")

        if not ask_bool("Add another provider?", default=False):
            break

    banner("Step: Routing Strategy")
    routing_tiers = step_routing_strategy(onboarded)

    banner("Step: Brain Configuration")
    brain_entries = step_brain_config(onboarded)

    show_summary(onboarded, routing_tiers, brain_entries)
    print()
    if not ask_bool("Save everything?", default=True):
        warn("Wizard cancelled. Nothing was saved.")
        sys.exit(0)

    # Build and send the onboard payload
    payload = {
        "providers": onboarded,
        "routing_tiers": routing_tiers,
        "brain_entries": brain_entries,
    }
    info("Saving configuration...")
    try:
        result = _post("/admin/wizard/onboard", payload, token)
    except Exception as e:
        err(f"Failed to save: {e}")
        sys.exit(1)

    if result.get("ok"):
        banner("✅  Wizard Complete!")
        s = result["summary"]
        info(f"Providers   : {len(s.get('providers', []))}")
        info(f"Credentials : {len(s.get('credentials', []))}")
        info(f"Models      : {len(s.get('models', []))}")
        info(f"Routing     : {s.get('routing')}")
        info(f"Brain       : {len(s.get('brain', []))} entr{'y' if len(s.get('brain', [])) == 1 else 'ies'}")
        print()
        info("Open the dashboard to review: http://localhost:6565")
    else:
        err("Wizard returned an unexpected response.")
        print(json.dumps(result, indent=2))
        sys.exit(1)


def main():
    _load_env()

    token = _get_admin_token()
    if not token:
        err("No admin token found.")
        info("Create one with:  ./unifyroute create token admin")
        sys.exit(1)

    try:
        run_wizard(token)
    except KeyboardInterrupt:
        print()
        warn("Wizard interrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
