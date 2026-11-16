"""Database-backed login budgets shared by all application workers."""
import hashlib
import ipaddress
import time
import unicodedata

from sqlalchemy import text

WINDOW_SECONDS = 900
ACCOUNT_LIMIT = 10
IP_LIMIT = 60


def normalize_ip(value):
    if '%' in value:
        raise ValueError('Scoped addresses are not supported')
    address = ipaddress.ip_address(value.strip())
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return str(address)


def client_ip(request):
    # Uvicorn normalizes request.client only for configured trusted proxy peers.
    value = request.client.host if request.client else ""
    try:
        return normalize_ip(value)
    except ValueError:
        return "unknown"


def user_agent(request):
    return request.headers.get("user-agent", "").replace("\x00", "").strip()[:255]


def login_rules(db):
    row = db.execute(text('SELECT window_seconds, account_limit, ip_limit, version, updated_at '
                          'FROM auth_login_rules WHERE id=1')).mappings().first()
    return dict(row) if row else {'window_seconds': WINDOW_SECONDS, 'account_limit': ACCOUNT_LIMIT,
                                 'ip_limit': IP_LIMIT, 'version': 0, 'updated_at': None}


def blocked_login_retry(db, ip, now=None):
    now = int(time.time()) if now is None else now
    expiry = db.execute(text('SELECT expires_at FROM auth_ip_blocks WHERE ip_address=:ip'), {'ip': ip}).scalar()
    return max(0, int(expiry) - now) if expiry else 0


def ip_bucket_key(ip):
    return hashlib.sha256(('ip:' + ip).encode()).hexdigest()


def reserve_login_attempt(db, username, ip, now=None, details=None):
    now = int(time.time()) if now is None else now
    rules = login_rules(db)
    # IP budget is consumed first, limiting unknown-account bucket creation.
    retry = _consume(db, "ip:" + ip, rules['ip_limit'], now, rules['window_seconds'])
    if retry:
        if details is not None:
            details.update(dimension='ip', retry_after=retry)
        db.commit()
        return retry
    row = db.execute(text("SELECT id FROM auth_users WHERE username = :name"), {"name": username}).first()
    identity = "user:" + str(row[0]) if row else "name:" + unicodedata.normalize("NFKC", username).casefold()
    retry = _consume(db, identity, rules['account_limit'], now, rules['window_seconds'])
    if retry and details is not None:
        details.update(dimension='account', retry_after=retry)
    # Reserve attempts before password work, even if a process crashes or credentials are valid.
    db.commit()
    return retry


def _consume(db, identity, limit, now, window_seconds=WINDOW_SECONDS):
    key = hashlib.sha256(identity.encode()).hexdigest()
    dialect = db.get_bind().dialect.name
    suffix = "ON DUPLICATE KEY UPDATE bucket_key = bucket_key" if dialect == "mysql" else "ON CONFLICT(bucket_key) DO NOTHING"
    db.execute(text("INSERT INTO auth_login_limits (bucket_key, attempts, reset_at) VALUES (:key, 0, :reset) " + suffix),
               {"key": key, "reset": now + window_seconds})
    db.execute(text("""
        UPDATE auth_login_limits SET
          attempts = CASE WHEN reset_at <= :now THEN 1 WHEN attempts <= :limit THEN attempts + 1 ELSE attempts END,
          reset_at = CASE WHEN reset_at <= :now THEN :reset ELSE reset_at END
        WHERE bucket_key = :key
    """), {"key": key, "now": now, "reset": now + window_seconds, "limit": limit})
    # REPEATABLE READ can otherwise expose a stale snapshot after a capped/no-op update.
    locking = " FOR UPDATE" if dialect == "mysql" else ""
    row = db.execute(text("SELECT attempts, reset_at FROM auth_login_limits WHERE bucket_key = :key" + locking), {"key": key}).one()
    return max(1, row.reset_at - now) if row.attempts > limit else 0
