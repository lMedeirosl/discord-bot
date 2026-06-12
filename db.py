import sqlite3
import random
import os
import time
from config import DATABASE_PATH

SEED_ITEMS = [
    ("Osso",      50,  0),
    ("Bolinha",   80,  0),
    ("Ração",    120,  0),
    ("Coleira",  200,  0),
    ("Cobertor", 350,  0),
    ("Coroa",    500,  1),
    ("Capa Lendária", 750, 1),
]

ITEM_BONUSES: dict[str, dict[str, int]] = {
    "osso":           {"happiness": 2,  "power": 1},
    "bolinha":        {"happiness": 3,  "power": 0},
    "ração":          {"happiness": 2,  "power": 2},
    "coleira":        {"happiness": 1,  "power": 3},
    "cobertor":       {"happiness": 4,  "power": 1},
    "coroa":          {"happiness": 5,  "power": 8},
    "capa lendária":  {"happiness": 6,  "power": 10},
}


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_missing(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column not in cols


def initialize_database() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT UNIQUE NOT NULL,
                balance    INTEGER NOT NULL DEFAULT 0,
                last_daily INTEGER DEFAULT NULL,
                last_work  INTEGER DEFAULT NULL
            )
        """)
        for col in ("last_daily", "last_work"):
            if _column_missing(conn, "users", col):
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT NULL")
        if _column_missing(conn, "users", "daily_streak"):
            conn.execute("ALTER TABLE users ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT UNIQUE NOT NULL,
                base_price    INTEGER NOT NULL,
                current_price INTEGER NOT NULL,
                demand        INTEGER NOT NULL DEFAULT 0,
                is_unique     INTEGER NOT NULL DEFAULT 0
            )
        """)
        for col in ("base_price", "current_price", "demand", "is_unique"):
            if _column_missing(conn, "items", col):
                if col == "base_price":
                    conn.execute("ALTER TABLE items ADD COLUMN base_price INTEGER NOT NULL DEFAULT 0")
                    conn.execute("UPDATE items SET base_price = price WHERE base_price = 0")
                elif col == "current_price":
                    conn.execute("ALTER TABLE items ADD COLUMN current_price INTEGER NOT NULL DEFAULT 0")
                    conn.execute("UPDATE items SET current_price = price WHERE current_price = 0")
                elif col == "demand":
                    conn.execute("ALTER TABLE items ADD COLUMN demand INTEGER NOT NULL DEFAULT 0")
                elif col == "is_unique":
                    conn.execute("ALTER TABLE items ADD COLUMN is_unique INTEGER NOT NULL DEFAULT 0")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  TEXT NOT NULL,
                item_id  INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                UNIQUE(user_id, item_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id              TEXT UNIQUE NOT NULL,
                mascot_name            TEXT NOT NULL DEFAULT 'Floq',
                level                  INTEGER NOT NULL DEFAULT 1,
                happiness              INTEGER NOT NULL DEFAULT 50,
                xp                     INTEGER NOT NULL DEFAULT 0,
                last_happiness_update  INTEGER DEFAULT NULL,
                bank                   INTEGER NOT NULL DEFAULT 0,
                power                  INTEGER NOT NULL DEFAULT 0,
                mood                   TEXT DEFAULT 'neutral',
                victories              INTEGER NOT NULL DEFAULT 0
            )
        """)
        for col in ("last_happiness_update", "bank", "power", "mood", "victories"):
            if _column_missing(conn, "servers", col):
                if col == "last_happiness_update":
                    conn.execute("ALTER TABLE servers ADD COLUMN last_happiness_update INTEGER DEFAULT NULL")
                elif col == "bank":
                    conn.execute("ALTER TABLE servers ADD COLUMN bank INTEGER NOT NULL DEFAULT 0")
                elif col == "power":
                    conn.execute("ALTER TABLE servers ADD COLUMN power INTEGER NOT NULL DEFAULT 0")
                elif col == "mood":
                    conn.execute("ALTER TABLE servers ADD COLUMN mood TEXT DEFAULT 'neutral'")
                elif col == "victories":
                    conn.execute("ALTER TABLE servers ADD COLUMN victories INTEGER NOT NULL DEFAULT 0")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS server_missions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id  TEXT NOT NULL,
                goal       INTEGER NOT NULL,
                progress   INTEGER NOT NULL DEFAULT 0,
                reward     INTEGER NOT NULL,
                active     INTEGER NOT NULL DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS mascot_items (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                item_id   INTEGER NOT NULL,
                equipped  INTEGER NOT NULL DEFAULT 0,
                UNIQUE(server_id, item_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS global_ownership (
                item_id   INTEGER PRIMARY KEY,
                server_id TEXT NOT NULL
            )
        """)

        # marketplace
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_listings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id  TEXT NOT NULL,
                item_id    INTEGER NOT NULL,
                price      INTEGER NOT NULL,
                listed_at  INTEGER NOT NULL
            )
        """)

        # jobs (Prompt 9)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id TEXT NOT NULL,
                worker_id  TEXT DEFAULT NULL,
                payment    INTEGER NOT NULL,
                completed  INTEGER NOT NULL DEFAULT 0,
                accepted   INTEGER NOT NULL DEFAULT 0
            )
        """)

        # guilds (Prompt 11)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guilds (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT UNIQUE NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_members (
                guild_id   INTEGER NOT NULL,
                server_id  TEXT NOT NULL,
                UNIQUE(guild_id, server_id),
                UNIQUE(server_id)
            )
        """)

        # activity (Prompt 12)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS server_activity (
                server_id      TEXT PRIMARY KEY,
                messages       INTEGER NOT NULL DEFAULT 0,
                commands_used  INTEGER NOT NULL DEFAULT 0,
                last_active    INTEGER NOT NULL DEFAULT 0
            )
        """)

        # rotação de loja
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_rotation (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id     INTEGER NOT NULL UNIQUE,
                rotated_at  INTEGER NOT NULL
            )
        """)

        # aventuras narrativas do Floq
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adventures (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id      TEXT NOT NULL,
                title          TEXT NOT NULL,
                description    TEXT NOT NULL,
                goal           INTEGER NOT NULL,
                progress       INTEGER NOT NULL DEFAULT 0,
                reward_coins   INTEGER NOT NULL DEFAULT 0,
                reward_xp      INTEGER NOT NULL DEFAULT 0,
                started_at     INTEGER NOT NULL,
                ended_at       INTEGER DEFAULT NULL,
                success        INTEGER DEFAULT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adventure_participants (
                adventure_id   INTEGER NOT NULL,
                user_id        TEXT NOT NULL,
                contribution   INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (adventure_id, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS floq_memory (
                server_id      TEXT PRIMARY KEY,
                last_user_id   TEXT DEFAULT NULL,
                last_action    TEXT DEFAULT NULL,
                updated_at     INTEGER DEFAULT NULL
            )
        """)

        for name, price, is_unique in SEED_ITEMS:
            conn.execute(
                "INSERT OR IGNORE INTO items (name, base_price, current_price, demand, is_unique) VALUES (?, ?, ?, 0, ?)",
                (name, price, price, is_unique)
            )

        conn.commit()
        initialize_new_tables()


# ── users ──────────────────────────────────────────────────────────────────

def get_user(user_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def create_user(user_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)",
            (user_id,)
        )
        conn.commit()


def ensure_user(user_id: str) -> None:
    if get_user(user_id) is None:
        create_user(user_id)


def get_balance(user_id: str) -> int:
    ensure_user(user_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["balance"] if row else 0


def update_balance(user_id: str, amount: int) -> int:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        conn.commit()
    return get_balance(user_id)


def remove_balance(user_id: str, amount: int) -> int:
    return update_balance(user_id, -amount)


# ── timestamps ─────────────────────────────────────────────────────────────

def _get_timestamp(user_id: str, column: str) -> int | None:
    user = get_user(user_id)
    return user[column] if user else None


def _set_timestamp(user_id: str, column: str, timestamp: int) -> None:
    timestamp = int(timestamp)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE users SET {column} = ? WHERE user_id = ?",
            (timestamp, user_id)
        )
        conn.commit()


def get_last_daily(user_id: str) -> int | None:
    return _get_timestamp(user_id, "last_daily")


def update_last_daily(user_id: str, timestamp: int) -> None:
    _set_timestamp(user_id, "last_daily", timestamp)


def get_daily_streak(user_id: str) -> int:
    user = get_user(user_id)
    return user["daily_streak"] if user and user["daily_streak"] is not None else 0


def bump_daily_streak(user_id: str, keep_streak: bool) -> int:
    """
    Atualiza o streak: incrementa se keep_streak=True, reseta para 1 caso contrário.
    Retorna o novo valor do streak.
    """
    current = get_daily_streak(user_id)
    new_streak = current + 1 if keep_streak else 1
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET daily_streak = ? WHERE user_id = ?",
            (new_streak, user_id)
        )
        conn.commit()
    return new_streak


def get_last_work(user_id: str) -> int | None:
    return _get_timestamp(user_id, "last_work")


def update_last_work(user_id: str, timestamp: int) -> None:
    _set_timestamp(user_id, "last_work", timestamp)


# ── items ──────────────────────────────────────────────────────────────────

def get_all_items() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM items ORDER BY current_price ASC"
        ).fetchall()


def get_item(item_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()


def get_item_by_name(name: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM items WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()


def update_item_price(item_id: int, new_price: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE items SET current_price = ? WHERE id = ?",
            (new_price, item_id)
        )
        conn.commit()


def _recalculate_price(item_id: int, conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT base_price, demand FROM items WHERE id = ?", (item_id,)
    ).fetchone()
    return row["base_price"] + (row["demand"] * 5)


def increase_demand(item_id: int) -> int:
    with get_connection() as conn:
        conn.execute(
            "UPDATE items SET demand = demand + 1 WHERE id = ?", (item_id,)
        )
        new_price = _recalculate_price(item_id, conn)
        conn.execute(
            "UPDATE items SET current_price = ? WHERE id = ?", (new_price, item_id)
        )
        conn.commit()
    return new_price


def decrease_demand(item_id: int) -> int:
    with get_connection() as conn:
        conn.execute(
            "UPDATE items SET demand = MAX(0, demand - 1) WHERE id = ?", (item_id,)
        )
        new_price = _recalculate_price(item_id, conn)
        conn.execute(
            "UPDATE items SET current_price = ? WHERE id = ?", (new_price, item_id)
        )
        conn.commit()
    return new_price


def apply_global_modifier(multiplier: float) -> None:
    with get_connection() as conn:
        items = conn.execute("SELECT id, base_price, demand FROM items").fetchall()
        for item in items:
            dynamic_price = item["base_price"] + (item["demand"] * 5)
            modified_price = max(item["base_price"], int(dynamic_price * multiplier))
            conn.execute(
                "UPDATE items SET current_price = ? WHERE id = ?",
                (modified_price, item["id"])
            )
        conn.commit()


def reset_prices_to_dynamic() -> None:
    with get_connection() as conn:
        items = conn.execute("SELECT id, base_price, demand FROM items").fetchall()
        for item in items:
            price = item["base_price"] + (item["demand"] * 5)
            conn.execute(
                "UPDATE items SET current_price = ? WHERE id = ?",
                (price, item["id"])
            )
        conn.commit()


# ── global ownership (unique items) ────────────────────────────────────────

def get_unique_item_owner(item_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT server_id FROM global_ownership WHERE item_id = ?", (item_id,)
        ).fetchone()
    return row["server_id"] if row else None


def register_unique_ownership(item_id: int, server_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO global_ownership (item_id, server_id) VALUES (?, ?)",
            (item_id, server_id)
        )
        conn.commit()


def get_all_unique_items() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT i.id, i.name, i.current_price, go.server_id AS owner_server_id
            FROM items i
            LEFT JOIN global_ownership go ON go.item_id = i.id
            WHERE i.is_unique = 1
            ORDER BY i.base_price DESC
        """).fetchall()


# ── inventory (users) ──────────────────────────────────────────────────────

def add_item_to_inventory(user_id: str, item_id: int) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO inventory (user_id, item_id, quantity)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, item_id)
            DO UPDATE SET quantity = quantity + 1
        """, (user_id, item_id))
        conn.commit()


def get_user_inventory(user_id: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT i.name, i.current_price AS price, inv.quantity
            FROM inventory inv
            JOIN items i ON i.id = inv.item_id
            WHERE inv.user_id = ?
            ORDER BY i.name ASC
        """, (user_id,)).fetchall()


# ── mascot items (server equip system) ────────────────────────────────────

def add_item_to_mascot_inventory(server_id: str, item_id: int) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO mascot_items (server_id, item_id, equipped)
            VALUES (?, ?, 0)
            ON CONFLICT(server_id, item_id) DO NOTHING
        """, (server_id, item_id))
        conn.commit()


def remove_item_from_mascot_inventory(server_id: str, item_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM mascot_items WHERE server_id = ? AND item_id = ?",
            (server_id, item_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def equip_mascot_item(server_id: str, item_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM mascot_items WHERE server_id = ? AND item_id = ?",
            (server_id, item_id)
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            "UPDATE mascot_items SET equipped = 1 WHERE server_id = ? AND item_id = ?",
            (server_id, item_id)
        )
        conn.commit()
    return True


def unequip_mascot_item(server_id: str, item_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM mascot_items WHERE server_id = ? AND item_id = ?",
            (server_id, item_id)
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            "UPDATE mascot_items SET equipped = 0 WHERE server_id = ? AND item_id = ?",
            (server_id, item_id)
        )
        conn.commit()
    return True


def get_mascot_equipped_items(server_id: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT i.id, i.name, i.is_unique
            FROM mascot_items mi
            JOIN items i ON i.id = mi.item_id
            WHERE mi.server_id = ? AND mi.equipped = 1
            ORDER BY i.name ASC
        """, (server_id,)).fetchall()


def get_mascot_inventory(server_id: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT i.id, i.name, i.is_unique, mi.equipped
            FROM mascot_items mi
            JOIN items i ON i.id = mi.item_id
            WHERE mi.server_id = ?
            ORDER BY i.name ASC
        """, (server_id,)).fetchall()


def get_equipped_bonuses(server_id: str) -> dict[str, int]:
    equipped = get_mascot_equipped_items(server_id)
    total_happiness = 0
    total_power = 0
    for item in equipped:
        bonuses = ITEM_BONUSES.get(item["name"].lower(), {})
        total_happiness += bonuses.get("happiness", 0)
        total_power     += bonuses.get("power", 0)
    return {"happiness": total_happiness, "power": total_power}


# ── servers / mascot ───────────────────────────────────────────────────────

def get_server(server_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM servers WHERE server_id = ?", (server_id,)
        ).fetchone()


def create_server(server_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO servers (server_id) VALUES (?)",
            (server_id,)
        )
        conn.commit()


def ensure_server(server_id: str) -> None:
    if get_server(server_id) is None:
        create_server(server_id)


def get_mascot(server_id: str) -> sqlite3.Row:
    ensure_server(server_id)
    return get_server(server_id)


def get_happiness(server_id: str) -> int:
    ensure_server(server_id)
    return get_server(server_id)["happiness"]


def update_happiness(server_id: str, value: int) -> int:
    ensure_server(server_id)
    with get_connection() as conn:
        conn.execute("""
            UPDATE servers
            SET happiness = MAX(0, MIN(100, ?))
            WHERE server_id = ?
        """, (value, server_id))
        conn.commit()
    update_mood(server_id)
    return get_server(server_id)["happiness"]


def add_happiness(server_id: str, amount: int) -> int:
    ensure_server(server_id)
    bonuses = get_equipped_bonuses(server_id)
    effective = amount + bonuses["happiness"] if amount > 0 else amount
    with get_connection() as conn:
        conn.execute("""
            UPDATE servers
            SET happiness = MAX(0, MIN(100, happiness + ?))
            WHERE server_id = ?
        """, (effective, server_id))
        conn.commit()
    update_mood(server_id)
    return get_server(server_id)["happiness"]


def get_last_happiness_update(server_id: str) -> int | None:
    ensure_server(server_id)
    return get_server(server_id)["last_happiness_update"]


def set_last_happiness_update(server_id: str, timestamp: int) -> None:
    ensure_server(server_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE servers SET last_happiness_update = ? WHERE server_id = ?",
            (timestamp, server_id)
        )
        conn.commit()


def add_xp(server_id: str, amount: int) -> tuple[int, int]:
    ensure_server(server_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE servers SET xp = xp + ? WHERE server_id = ?",
            (amount, server_id)
        )
        conn.commit()
    row = get_server(server_id)
    xp    = row["xp"]
    level = row["level"]
    xp_threshold = level * 100
    if xp >= xp_threshold:
        with get_connection() as conn:
            conn.execute("""
                UPDATE servers
                SET level = level + 1, xp = xp - ?
                WHERE server_id = ?
            """, (xp_threshold, server_id))
            conn.commit()
        row   = get_server(server_id)
        xp    = row["xp"]
        level = row["level"]
    update_mood(server_id)
    return xp, level


def update_mood(server_id: str) -> str:
    ensure_server(server_id)
    row = get_server(server_id)
    happiness = row["happiness"]
    # mood based on happiness + random chaotic chance
    if happiness >= 70:
        mood = "happy"
    elif happiness >= 30:
        # 20% chance to be chaotic when neutral
        if random.random() < 0.2:
            mood = "chaotic"
        else:
            mood = "neutral"
    else:
        mood = "sad"
    with get_connection() as conn:
        conn.execute(
            "UPDATE servers SET mood = ? WHERE server_id = ?",
            (mood, server_id)
        )
        conn.commit()
    return mood


def get_mood(server_id: str) -> str:
    ensure_server(server_id)
    return get_server(server_id)["mood"]


def add_victory(server_id: str) -> None:
    ensure_server(server_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE servers SET victories = victories + 1 WHERE server_id = ?",
            (server_id,)
        )
        conn.commit()


def get_victories(server_id: str) -> int:
    ensure_server(server_id)
    return get_server(server_id)["victories"]


def get_server_score(server_id: str) -> int:
    """Calculate current score for ranking (level*50 + happiness*2 + victories*100)"""
    ensure_server(server_id)
    row = get_server(server_id)
    return row["level"] * 50 + row["happiness"] * 2 + row["victories"] * 100


def get_all_servers_scores() -> list[tuple[str, int]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT server_id, level, happiness, victories FROM servers"
        ).fetchall()
    scores = [(r["server_id"], r["level"]*50 + r["happiness"]*2 + r["victories"]*100) for r in rows]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def reset_season() -> list[tuple[str, int]]:
    """Reset victories for all servers and return top 3 scores before reset"""
    scores = get_all_servers_scores()
    with get_connection() as conn:
        conn.execute("UPDATE servers SET victories = 0")
        conn.commit()
    return scores[:3]


# ── server bank ────────────────────────────────────────────────────────────

def get_server_bank(server_id: str) -> int:
    ensure_server(server_id)
    return get_server(server_id)["bank"]


def add_to_server_bank(server_id: str, amount: int) -> int:
    ensure_server(server_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE servers SET bank = bank + ? WHERE server_id = ?",
            (amount, server_id)
        )
        conn.commit()
    return get_server_bank(server_id)


def remove_from_server_bank(server_id: str, amount: int) -> int:
    ensure_server(server_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE servers SET bank = MAX(0, bank - ?) WHERE server_id = ?",
            (amount, server_id)
        )
        conn.commit()
    return get_server_bank(server_id)


# ── server missions ────────────────────────────────────────────────────────

def create_mission(server_id: str, goal: int, reward: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE server_missions SET active = 0 WHERE server_id = ? AND active = 1",
            (server_id,)
        )
        conn.execute(
            "INSERT INTO server_missions (server_id, goal, progress, reward, active) VALUES (?, ?, 0, ?, 1)",
            (server_id, goal, reward)
        )
        conn.commit()


def get_active_mission(server_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM server_missions WHERE server_id = ? AND active = 1",
            (server_id,)
        ).fetchone()


def update_mission_progress(server_id: str, amount: int) -> sqlite3.Row | None:
    mission = get_active_mission(server_id)
    if mission is None:
        return None
    with get_connection() as conn:
        conn.execute(
            "UPDATE server_missions SET progress = progress + ? WHERE id = ?",
            (amount, mission["id"])
        )
        conn.commit()
    return get_active_mission(server_id)


def complete_mission(server_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE server_missions SET active = 0 WHERE server_id = ? AND active = 1",
            (server_id,)
        )
        conn.commit()


# ── pvp power ──────────────────────────────────────────────────────────────

def get_power(server_id: str) -> int:
    ensure_server(server_id)
    row = get_server(server_id)
    bonuses = get_equipped_bonuses(server_id)
    return row["level"] * 10 + row["happiness"] + bonuses["power"]


# ── marketplace ────────────────────────────────────────────────────────────

def create_listing(server_id: str, item_id: int, price: int) -> int | None:
    with get_connection() as conn:
        owned = conn.execute(
            "SELECT 1 FROM mascot_items WHERE server_id = ? AND item_id = ?",
            (server_id, item_id)
        ).fetchone()
        if not owned:
            return None
        conn.execute(
            "DELETE FROM mascot_items WHERE server_id = ? AND item_id = ?",
            (server_id, item_id)
        )
        conn.execute(
            "DELETE FROM global_ownership WHERE item_id = ? AND server_id = ?",
            (item_id, server_id)
        )
        cursor = conn.execute(
            "INSERT INTO market_listings (server_id, item_id, price, listed_at) VALUES (?, ?, ?, ?)",
            (server_id, item_id, price, int(time.time()))
        )
        conn.commit()
        return cursor.lastrowid


def remove_listing(listing_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM market_listings WHERE id = ?", (listing_id,))
        conn.commit()


def get_listing(listing_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("""
            SELECT ml.*, i.name, i.is_unique
            FROM market_listings ml
            JOIN items i ON i.id = ml.item_id
            WHERE ml.id = ?
        """, (listing_id,)).fetchone()


def get_all_listings() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT ml.id, ml.server_id, ml.item_id, ml.price, ml.listed_at,
                   i.name, i.is_unique,
                   s.mascot_name AS seller_name
            FROM market_listings ml
            JOIN items i ON i.id = ml.item_id
            LEFT JOIN servers s ON s.server_id = ml.server_id
            ORDER BY ml.price ASC
        """).fetchall()


def buy_listing(buyer_server_id: str, listing_id: int) -> bool:
    with get_connection() as conn:
        listing = conn.execute(
            "SELECT * FROM market_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        if not listing:
            return False
        seller_id = listing["server_id"]
        item_id   = listing["item_id"]
        price     = listing["price"]

        buyer_bank = conn.execute(
            "SELECT bank FROM servers WHERE server_id = ?", (buyer_server_id,)
        ).fetchone()
        if not buyer_bank or buyer_bank["bank"] < price:
            return False

        conn.execute(
            "UPDATE servers SET bank = bank - ? WHERE server_id = ?",
            (price, buyer_server_id)
        )
        conn.execute(
            "UPDATE servers SET bank = bank + ? WHERE server_id = ?",
            (price, seller_id)
        )

        conn.execute(
            "INSERT INTO mascot_items (server_id, item_id, equipped) VALUES (?, ?, 0)",
            (buyer_server_id, item_id)
        )
        item = conn.execute("SELECT is_unique FROM items WHERE id = ?", (item_id,)).fetchone()
        if item and item["is_unique"]:
            conn.execute(
                "INSERT OR REPLACE INTO global_ownership (item_id, server_id) VALUES (?, ?)",
                (item_id, buyer_server_id)
            )

        conn.execute("DELETE FROM market_listings WHERE id = ?", (listing_id,))
        conn.commit()
        return True


# ── jobs (Prompt 9) ────────────────────────────────────────────────────────

def create_job(creator_id: str, payment: int) -> int | None:
    """Create a job, deduct payment from creator immediately. Returns job id."""
    balance = get_balance(creator_id)
    if balance < payment:
        return None
    remove_balance(creator_id, payment)
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO jobs (creator_id, payment, completed, accepted) VALUES (?, ?, 0, 0)",
            (creator_id, payment)
        )
        conn.commit()
        return cursor.lastrowid


def get_pending_jobs() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM jobs WHERE completed = 0 AND accepted = 0"
        ).fetchall()


def get_job(job_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()


def accept_job(job_id: int, worker_id: str) -> bool:
    with get_connection() as conn:
        job = conn.execute(
            "SELECT * FROM jobs WHERE id = ? AND completed = 0 AND accepted = 0",
            (job_id,)
        ).fetchone()
        if not job:
            return False
        conn.execute(
            "UPDATE jobs SET worker_id = ?, accepted = 1 WHERE id = ?",
            (worker_id, job_id)
        )
        conn.commit()
        return True


def complete_job(job_id: int, worker_id: str) -> bool:
    with get_connection() as conn:
        job = conn.execute(
            "SELECT * FROM jobs WHERE id = ? AND completed = 0 AND accepted = 1 AND worker_id = ?",
            (job_id, worker_id)
        ).fetchone()
        if not job:
            return False
        # payment already deducted from creator, now give to worker
        update_balance(worker_id, job["payment"])
        conn.execute(
            "UPDATE jobs SET completed = 1 WHERE id = ?", (job_id,)
        )
        conn.commit()
        return True


# ── guilds (Prompt 11) ─────────────────────────────────────────────────────

def create_guild(name: str, creator_server_id: str) -> int | None:
    """Create a guild. Returns guild id or None if name exists or server already in guild."""
    with get_connection() as conn:
        existing = conn.execute("SELECT 1 FROM guild_members WHERE server_id = ?", (creator_server_id,)).fetchone()
        if existing:
            return None
        existing_name = conn.execute("SELECT 1 FROM guilds WHERE name = ?", (name,)).fetchone()
        if existing_name:
            return None
        cursor = conn.execute(
            "INSERT INTO guilds (name, created_at) VALUES (?, ?)",
            (name, int(time.time()))
        )
        guild_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO guild_members (guild_id, server_id) VALUES (?, ?)",
            (guild_id, creator_server_id)
        )
        conn.commit()
        return guild_id


def join_guild(guild_id: int, server_id: str) -> bool:
    with get_connection() as conn:
        # check if server already in guild
        existing = conn.execute("SELECT 1 FROM guild_members WHERE server_id = ?", (server_id,)).fetchone()
        if existing:
            return False
        # check guild size
        count = conn.execute("SELECT COUNT(*) as c FROM guild_members WHERE guild_id = ?", (guild_id,)).fetchone()
        if count["c"] >= 4:
            return False
        conn.execute(
            "INSERT INTO guild_members (guild_id, server_id) VALUES (?, ?)",
            (guild_id, server_id)
        )
        conn.commit()
        return True


def get_server_guild(server_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT g.* FROM guilds g
            JOIN guild_members gm ON gm.guild_id = g.id
            WHERE gm.server_id = ?
        """, (server_id,)).fetchone()
        return row


def get_guild_members(guild_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT server_id FROM guild_members WHERE guild_id = ?", (guild_id,)
        ).fetchall()


def get_guild_by_name(name: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM guilds WHERE name = ?", (name,)).fetchone()


def get_guild_by_id(guild_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM guilds WHERE id = ?", (guild_id,)).fetchone()


def get_guild_power(guild_id: int) -> int:
    members = get_guild_members(guild_id)
    total = 0
    for m in members:
        total += get_power(m["server_id"])
    return total


def get_all_guilds_ranked() -> list[dict]:
    """Retorna todas as guildas ordenadas por poder total (maior primeiro)."""
    with get_connection() as conn:
        guilds = conn.execute("SELECT * FROM guilds").fetchall()

    ranked = []
    for g in guilds:
        members = get_guild_members(g["id"])
        total_power = sum(get_power(m["server_id"]) for m in members)
        ranked.append({
            "id": g["id"],
            "name": g["name"],
            "total_power": total_power,
            "member_count": len(members),
        })

    ranked.sort(key=lambda x: x["total_power"], reverse=True)
    return ranked


# ── activity (Prompt 12) ───────────────────────────────────────────────────

def record_message(server_id: str) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO server_activity (server_id, messages, commands_used, last_active)
            VALUES (?, 1, 0, ?)
            ON CONFLICT(server_id) DO UPDATE SET
                messages = messages + 1,
                last_active = ?
        """, (server_id, int(time.time()), int(time.time())))
        conn.commit()


def record_command(server_id: str) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO server_activity (server_id, messages, commands_used, last_active)
            VALUES (?, 0, 1, ?)
            ON CONFLICT(server_id) DO UPDATE SET
                commands_used = commands_used + 1,
                last_active = ?
        """, (server_id, int(time.time()), int(time.time())))
        conn.commit()


def get_activity(server_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM server_activity WHERE server_id = ?", (server_id,)
        ).fetchone()


def reset_activity(server_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE server_activity SET messages = 0, commands_used = 0 WHERE server_id = ?",
            (server_id,)
        )
        conn.commit()
# ========== NOVAS TABELAS E FUNÇÕES (adicione no final do seu db.py) ==========

def initialize_new_tables():
    """Chame essa função dentro do seu initialize_database() existente"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                rarity TEXT NOT NULL,
                slot TEXT,
                stats TEXT,
                image_path TEXT,
                base_price INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_items (
                user_id TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, item_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS equipped_items (
                user_id TEXT NOT NULL,
                slot TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, slot)
            )
        """)
        conn.commit()

# ---- Funções do novo sistema de itens ----
def add_user_item(user_id, item_id, quantity=1):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO user_items (user_id, item_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + ?
        """, (user_id, item_id, quantity, quantity))
        conn.commit()

def remove_user_item(user_id, item_id, quantity=1):
    with get_connection() as conn:
        cur = conn.execute("SELECT quantity FROM user_items WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        row = cur.fetchone()
        if row and row["quantity"] >= quantity:
            new_qty = row["quantity"] - quantity
            if new_qty == 0:
                conn.execute("DELETE FROM user_items WHERE user_id = ? AND item_id = ?", (user_id, item_id))
            else:
                conn.execute("UPDATE user_items SET quantity = ? WHERE user_id = ? AND item_id = ?", (new_qty, user_id, item_id))
            conn.commit()
            return True
        return False

def get_user_items(user_id, page=1, per_page=10):
    with get_connection() as conn:
        offset = (page-1) * per_page
        return conn.execute("""
            SELECT i.id, i.name, i.type, i.rarity, i.slot, ui.quantity
            FROM user_items ui
            JOIN items_new i ON i.id = ui.item_id
            WHERE ui.user_id = ?
            LIMIT ? OFFSET ?
        """, (user_id, per_page, offset)).fetchall()

def count_user_items(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM user_items WHERE user_id = ?", (user_id,)).fetchone()
        return row["cnt"] if row else 0

def equip_item(user_id, item_id):
    with get_connection() as conn:
        own = conn.execute("SELECT 1 FROM user_items WHERE user_id = ? AND item_id = ? AND quantity > 0", (user_id, item_id)).fetchone()
        if not own:
            return False
        item = conn.execute("SELECT slot FROM items_new WHERE id = ?", (item_id,)).fetchone()
        if not item or not item["slot"]:
            return False
        conn.execute("DELETE FROM equipped_items WHERE user_id = ? AND slot = ?", (user_id, item["slot"]))
        conn.execute("INSERT INTO equipped_items (user_id, slot, item_id) VALUES (?, ?, ?)", (user_id, item["slot"], item_id))
        conn.commit()
        return True

def unequip_item(user_id, slot):
    with get_connection() as conn:
        conn.execute("DELETE FROM equipped_items WHERE user_id = ? AND slot = ?", (user_id, slot))
        conn.commit()
        return True

def get_equipped_items(user_id):
    with get_connection() as conn:
        return conn.execute("""
            SELECT i.id, i.name, i.type, i.rarity, i.slot, i.image_path, i.stats
            FROM equipped_items e
            JOIN items_new i ON i.id = e.item_id
            WHERE e.user_id = ?
        """, (user_id,)).fetchall()

def get_new_item(item_id):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM items_new WHERE id = ?", (item_id,)).fetchone()

def get_new_item_by_name(name):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM items_new WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()


# ── aventuras narrativas ───────────────────────────────────────────────────

def create_adventure(server_id: str, title: str, description: str,
                     goal: int, reward_coins: int, reward_xp: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO adventures (server_id, title, description, goal,
                                    reward_coins, reward_xp, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (server_id, title, description, goal, reward_coins, reward_xp, int(time.time())))
        conn.commit()
        return cursor.lastrowid


def get_active_adventure(server_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM adventures
            WHERE server_id = ? AND ended_at IS NULL
            ORDER BY started_at DESC LIMIT 1
        """, (server_id,)).fetchone()


def contribute_adventure(adventure_id: int, user_id: str, amount: int) -> sqlite3.Row | None:
    """Add contribution from user. Returns updated adventure row."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO adventure_participants (adventure_id, user_id, contribution)
            VALUES (?, ?, ?)
            ON CONFLICT(adventure_id, user_id)
            DO UPDATE SET contribution = contribution + ?
        """, (adventure_id, user_id, amount, amount))
        conn.execute("""
            UPDATE adventures SET progress = progress + ? WHERE id = ?
        """, (amount, adventure_id))
        conn.commit()
        return conn.execute("SELECT * FROM adventures WHERE id = ?", (adventure_id,)).fetchone()


def end_adventure(adventure_id: int, success: bool) -> None:
    with get_connection() as conn:
        conn.execute("""
            UPDATE adventures SET ended_at = ?, success = ? WHERE id = ?
        """, (int(time.time()), 1 if success else 0, adventure_id))
        conn.commit()


def get_adventure_participants(adventure_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM adventure_participants WHERE adventure_id = ?
            ORDER BY contribution DESC
        """, (adventure_id,)).fetchall()


def get_last_adventures(server_id: str, limit: int = 5) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM adventures WHERE server_id = ? AND ended_at IS NOT NULL
            ORDER BY ended_at DESC LIMIT ?
        """, (server_id, limit)).fetchall()


# ── memória do Floq ────────────────────────────────────────────────────────

def update_floq_memory(server_id: str, user_id: str, action: str) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO floq_memory (server_id, last_user_id, last_action, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(server_id) DO UPDATE SET
                last_user_id = ?,
                last_action  = ?,
                updated_at   = ?
        """, (server_id, user_id, action, int(time.time()),
              user_id, action, int(time.time())))
        conn.commit()


def get_floq_memory(server_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM floq_memory WHERE server_id = ?", (server_id,)
        ).fetchone()


# ── rotação de loja ────────────────────────────────────────────────────────

SHOP_ROTATION_HOURS = 1        # nova rotação a cada 1 hora
SHOP_SIZE_BY_RARITY = {        # quantos de cada raridade aparecem por vez
    "common":    3,
    "uncommon":  3,
    "rare":      2,
    "epic":      1,
    "legendary": 1,
}


def _pick_shop_items() -> list[int]:
    """Sorteia IDs da items_new respeitando cotas por raridade."""
    with get_connection() as conn:
        picked_ids: list[int] = []
        for rarity, qty in SHOP_SIZE_BY_RARITY.items():
            rows = conn.execute(
                "SELECT id FROM items_new WHERE rarity = ? ORDER BY RANDOM() LIMIT ?",
                (rarity, qty)
            ).fetchall()
            picked_ids.extend(r["id"] for r in rows)
    return picked_ids


def refresh_shop_rotation() -> None:
    """Força uma nova rotação imediatamente."""
    item_ids = _pick_shop_items()
    now = int(time.time())
    with get_connection() as conn:
        conn.execute("DELETE FROM shop_rotation")
        for item_id in item_ids:
            conn.execute(
                "INSERT OR IGNORE INTO shop_rotation (item_id, rotated_at) VALUES (?, ?)",
                (item_id, now)
            )
        conn.commit()


def get_shop_items() -> tuple[list[sqlite3.Row], int]:
    """
    Retorna (itens_da_loja, timestamp_da_rotacao).
    Rotaciona automaticamente se a janela de tempo venceu ou a tabela está vazia.
    """
    cutoff = int(time.time()) - SHOP_ROTATION_HOURS * 3600
    with get_connection() as conn:
        rotation = conn.execute(
            "SELECT rotated_at FROM shop_rotation LIMIT 1"
        ).fetchone()

    if not rotation or rotation["rotated_at"] < cutoff:
        refresh_shop_rotation()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT i.*, sr.rotated_at
            FROM shop_rotation sr
            JOIN items_new i ON i.id = sr.item_id
            ORDER BY
                CASE i.rarity
                    WHEN 'common'    THEN 1
                    WHEN 'uncommon'  THEN 2
                    WHEN 'rare'      THEN 3
                    WHEN 'epic'      THEN 4
                    WHEN 'legendary' THEN 5
                END,
                i.name
        """).fetchall()
        rotated_at = rows[0]["rotated_at"] if rows else int(time.time())
    return rows, rotated_at
