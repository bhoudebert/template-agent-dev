"""LLM provider adapters. Stdlib only. Pick with AGENT_PROVIDER or --provider.

openai : any OpenAI-compatible /chat/completions endpoint
         (Ollama, vLLM, llama.cpp server, LM Studio, OpenAI, gateways...)
         env: AGENT_BASE_URL (default http://localhost:11434/v1), AGENT_API_KEY,
              AGENT_MODEL_STRONG / AGENT_MODEL_CHEAP / AGENT_MODEL,
              AGENT_REASONING_EFFORT (none|low|medium|high, sent as reasoning_effort),
              AGENT_MAX_TOKENS (sent as max_tokens)
cmd    : pipe the prompt to any CLI on stdin, read the answer from stdout.
         env: AGENT_CMD  e.g. "claude -p", "codex exec -", "ollama run llama3"
dry    : no call; runner prints the prompt.
"""
import json
import os
import shlex
import subprocess
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    pass


def pick_model(tier):
    env = os.environ
    model = env.get(f"AGENT_MODEL_{tier.upper()}") or env.get("AGENT_MODEL")
    if not model:
        raise ProviderError(f"no model set: export AGENT_MODEL (or AGENT_MODEL_{tier.upper()})")
    return model


def _openai(system, user, tier):
    base = os.environ.get("AGENT_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    body = {
        "model": pick_model(tier),
        "temperature": 0.2,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if os.environ.get("AGENT_REASONING_EFFORT"):
        body["reasoning_effort"] = os.environ["AGENT_REASONING_EFFORT"]
    if os.environ.get("AGENT_MAX_TOKENS"):
        body["max_tokens"] = int(os.environ["AGENT_MAX_TOKENS"])
    headers = {"Content-Type": "application/json"}
    if os.environ.get("AGENT_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['AGENT_API_KEY']}"
    req = urllib.request.Request(f"{base}/chat/completions", json.dumps(body).encode(), headers)
    try:
        with urllib.request.urlopen(req, timeout=int(os.environ.get("AGENT_TIMEOUT", "600"))) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise ProviderError(f"openai provider HTTP {e.code} (model={body['model']!r}): {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ProviderError(f"openai provider failed: {e}") from e
    try:
        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
    except (KeyError, IndexError, AttributeError) as e:
        raise ProviderError(f"unexpected response shape: {str(data)[:300]}") from e
    if not content.strip():
        reasoning = choice["message"].get("reasoning") or choice["message"].get("reasoning_content") or ""
        raise ProviderError(
            f"model returned no text (finish_reason={choice.get('finish_reason')!r}, "
            f"reasoning chars={len(reasoning)}). A thinking model probably spent its whole budget reasoning: "
            "set AGENT_REASONING_EFFORT=none (or low), set AGENT_MAX_TOKENS, or use a non-thinking model.")
    return content


def _cmd(system, user, tier):
    cmd = os.environ.get("AGENT_CMD")
    if not cmd:
        raise ProviderError('AGENT_CMD not set (e.g. AGENT_CMD="claude -p")')
    proc = subprocess.run(
        shlex.split(cmd), input=f"{system}\n\n{user}", text=True, capture_output=True,
        timeout=int(os.environ.get("AGENT_TIMEOUT", "600")),
    )
    if proc.returncode != 0:
        raise ProviderError(f"AGENT_CMD exited {proc.returncode}: {proc.stderr[:300]}")
    return proc.stdout


PROVIDERS = {"openai": _openai, "cmd": _cmd}


def complete(system, user, tier="strong", provider=None):
    name = provider or os.environ.get("AGENT_PROVIDER", "openai")
    if name not in PROVIDERS:
        raise ProviderError(f"unknown provider {name!r}; choose from {sorted(PROVIDERS)} or 'dry'")
    return PROVIDERS[name](system, user, tier)
