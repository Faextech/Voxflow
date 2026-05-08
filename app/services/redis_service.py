"""
Redis Service — VoxFlow
Wrapper com fallback in-memory transparente quando Redis não está disponível.
Garante que o sistema funcione em dev sem Redis instalado.
"""
import json
import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis_client = None
_redis_available = False
_redis_check_lock = threading.Lock()

# Fallback in-memory store (usado quando Redis não está disponível)
_memory_store: dict = {}
_memory_expiry: dict = {}
_memory_lock = threading.Lock()


def _get_redis():
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client

    with _redis_check_lock:
        if _redis_client is not None:
            return _redis_client
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            logger.info("[REDIS] REDIS_URL não configurado — usando fallback in-memory")
            return None
        try:
            import redis
            client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=3)
            client.ping()
            _redis_client = client
            _redis_available = True
            logger.info("[REDIS] Conectado: %s", redis_url.split("@")[-1])
        except Exception as e:
            logger.warning("[REDIS] Não disponível (%s) — usando fallback in-memory", e)
            _redis_client = None
            _redis_available = False
    return _redis_client


def is_available() -> bool:
    return _get_redis() is not None


# ── Memory fallback helpers ───────────────────────────────────────────────────

def _mem_set(key: str, value: str, ex: Optional[int] = None):
    with _memory_lock:
        _memory_store[key] = value
        if ex:
            _memory_expiry[key] = time.time() + ex
        else:
            _memory_expiry.pop(key, None)


def _mem_get(key: str) -> Optional[str]:
    with _memory_lock:
        exp = _memory_expiry.get(key)
        if exp and time.time() > exp:
            _memory_store.pop(key, None)
            _memory_expiry.pop(key, None)
            return None
        return _memory_store.get(key)


def _mem_delete(*keys: str):
    with _memory_lock:
        for k in keys:
            _memory_store.pop(k, None)
            _memory_expiry.pop(k, None)


def _mem_exists(key: str) -> bool:
    return _mem_get(key) is not None


def _mem_expire(key: str, seconds: int):
    with _memory_lock:
        if key in _memory_store:
            _memory_expiry[key] = time.time() + seconds


def _mem_keys_prefix(prefix: str) -> list:
    with _memory_lock:
        now = time.time()
        result = []
        for k, v in list(_memory_store.items()):
            exp = _memory_expiry.get(k)
            if exp and now > exp:
                continue
            if k.startswith(prefix):
                result.append(k)
        return result


# ── Public API ────────────────────────────────────────────────────────────────

def set(key: str, value: Any, ex: Optional[int] = None) -> bool:
    """Define chave-valor. ex = TTL em segundos."""
    if not isinstance(value, str):
        value = json.dumps(value)
    r = _get_redis()
    if r:
        try:
            return bool(r.set(key, value, ex=ex))
        except Exception as e:
            logger.warning("[REDIS] set falhou: %s — usando memory", e)
    _mem_set(key, value, ex=ex)
    return True


def get(key: str) -> Optional[Any]:
    """Retorna valor ou None."""
    r = _get_redis()
    raw = None
    if r:
        try:
            raw = r.get(key)
        except Exception as e:
            logger.warning("[REDIS] get falhou: %s — usando memory", e)
            raw = _mem_get(key)
    else:
        raw = _mem_get(key)

    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def get_str(key: str) -> Optional[str]:
    """Retorna string bruta ou None."""
    r = _get_redis()
    if r:
        try:
            return r.get(key)
        except Exception:
            pass
    return _mem_get(key)


def delete(*keys: str) -> int:
    r = _get_redis()
    if r:
        try:
            return r.delete(*keys)
        except Exception as e:
            logger.warning("[REDIS] delete falhou: %s", e)
    _mem_delete(*keys)
    return len(keys)


def exists(key: str) -> bool:
    r = _get_redis()
    if r:
        try:
            return bool(r.exists(key))
        except Exception:
            pass
    return _mem_exists(key)


def expire(key: str, seconds: int) -> bool:
    r = _get_redis()
    if r:
        try:
            return bool(r.expire(key, seconds))
        except Exception:
            pass
    _mem_expire(key, seconds)
    return True


def keys_with_prefix(prefix: str) -> list:
    r = _get_redis()
    if r:
        try:
            return [k for k in r.scan_iter(f"{prefix}*")]
        except Exception:
            pass
    return _mem_keys_prefix(prefix)


def incr(key: str, ex: Optional[int] = None) -> int:
    r = _get_redis()
    if r:
        try:
            val = r.incr(key)
            if ex and val == 1:
                r.expire(key, ex)
            return val
        except Exception as e:
            logger.warning("[REDIS] incr falhou: %s", e)
    # fallback memory
    with _memory_lock:
        # Verifica se a chave já expirou antes de incrementar (evita contador "preso")
        exp = _memory_expiry.get(key)
        if exp and time.time() > exp:
            _memory_store.pop(key, None)
            _memory_expiry.pop(key, None)

        raw = _memory_store.get(key, "0")
        try:
            n = int(raw) + 1
        except ValueError:
            n = 1
        _memory_store[key] = str(n)
        if ex and n == 1:
            _memory_expiry[key] = time.time() + ex
        elif key not in _memory_expiry and ex:
            _memory_expiry[key] = time.time() + ex
        return n


def get_int(key: str) -> int:
    val = get_str(key)
    try:
        return int(val or 0)
    except (ValueError, TypeError):
        return 0


def hset(name: str, mapping: dict, ex: Optional[int] = None) -> bool:
    """Armazena hash como JSON serializado."""
    return set(name, mapping, ex=ex)


def hget(name: str) -> Optional[dict]:
    val = get(name)
    if isinstance(val, dict):
        return val
    return None


def setnx(key: str, value: Any = "1", ex: Optional[int] = None) -> bool:
    """SET if Not eXists (atômico). Retorna True se adquiriu, False se já existia. Usado como mutex."""
    if not isinstance(value, str):
        value = json.dumps(value)
    r = _get_redis()
    if r:
        try:
            ok = r.setnx(key, value)
            if ok and ex:
                r.expire(key, ex)
            return bool(ok)
        except Exception as e:
            logger.warning("[REDIS] setnx falhou: %s — usando memory", e)
    # Fallback memory: tenta adquirir com lock para atomicidade local
    with _memory_lock:
        if _mem_exists(key):
            return False
        _mem_set(key, value, ex=ex)
        return True


def sadd(key: str, *members: str, ex: Optional[int] = None) -> bool:
    """Adiciona membros a um set (armazenado como JSON list)."""
    current = get(key)
    if not isinstance(current, list):
        current = []
    for m in members:
        if m not in current:
            current.append(m)
    return set(key, current, ex=ex)


def sismember(key: str, member: str) -> bool:
    current = get(key)
    if isinstance(current, list):
        return member in current
    return False


def smembers(key: str) -> set:
    current = get(key)
    if isinstance(current, list):
        return set(current)
    return set()
