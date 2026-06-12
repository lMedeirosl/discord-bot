# item_manager.py
import json
import os
import logging
from config import ITEMS_JSON_DIR

logger = logging.getLogger(__name__)

_items_by_id = {}
_items_by_name = {}

def load_all_items():
    global _items_by_id, _items_by_name
    import db
    if not os.path.exists(ITEMS_JSON_DIR):
        os.makedirs(ITEMS_JSON_DIR, exist_ok=True)
        return
    for filename in os.listdir(ITEMS_JSON_DIR):
        if filename.endswith(".json"):
            path = os.path.join(ITEMS_JSON_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    if isinstance(items, list):
                        for item in items:
                            _insert_or_update_item(item)
                    else:
                        logger.error(f"Invalid items file {filename}: must contain array")
            except Exception as e:
                logger.error(f"Failed to load {filename}: {e}")
    refresh_cache()

def _insert_or_update_item(item_data):
    import db
    with db.get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO items_new (id, name, type, rarity, slot, stats, image_path, base_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_data.get("id"),
            item_data["name"],
            item_data["type"],
            item_data["rarity"],
            item_data.get("slot"),
            json.dumps(item_data.get("stats", {})),
            item_data.get("image_path", ""),
            item_data.get("base_price", 0)
        ))
        conn.commit()

def refresh_cache():
    global _items_by_id, _items_by_name
    import db
    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM items_new").fetchall()
        _items_by_id = {row["id"]: dict(row) for row in rows}
        _items_by_name = {row["name"].lower(): dict(row) for row in rows}

def get_item(item_id):
    return _items_by_id.get(item_id)

def get_item_by_name(name):
    return _items_by_name.get(name.lower())

def get_all_items():
    return list(_items_by_id.values())
