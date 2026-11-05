"""Sign bounded, private continuation state for one mate search."""

import hashlib
import hmac

from itsdangerous import BadData, URLSafeSerializer

from .fact_fingerprint import canonical

MAX_SEEN = 64
MAX_TOKEN = 16384
VERSION = "mate-search-v1"


def _signer(secret):
    return URLSafeSerializer(secret, salt=VERSION)


def encode(secret, state):
    token = _signer(secret).dumps(state)
    if len(token) > MAX_TOKEN:
        raise ValueError("search continuation limit reached")
    return token


def decode(secret, token):
    try:
        if not isinstance(token, str) or len(token) > MAX_TOKEN:
            raise ValueError
        state = _signer(secret).loads(token)
        if not isinstance(state, dict) or state.get("version") != VERSION:
            raise ValueError
        return state
    except (BadData, TypeError, ValueError):
        raise ValueError("search continuation changed; restart") from None


def fingerprint(secret, kind, value):
    return hmac.new(secret, canonical([kind, value]).encode(), hashlib.sha256).hexdigest()


def seen(secret, ordered):
    prompts = {fingerprint(secret, "prompt", item["prompt_key"]) for item in ordered}
    games = {fingerprint(secret, "game", item["game"]) for item in ordered if item.get("game")}
    return sorted(prompts), sorted(games)


def within_limit(prompts, games):
    return len(prompts) <= MAX_SEEN and len(games) <= MAX_SEEN
