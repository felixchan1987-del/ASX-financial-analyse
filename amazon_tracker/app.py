import os
import sqlite3
import threading
import time
from flask import Flask, g, jsonify, render_template, request

from scraper import fetch_product, normalize_url

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "tracker.db")
REFRESH_INTERVAL_HOURS = 12


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = _connect()
    return g.db


@app.teardown_appcontext
def close_db(_=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            url        TEXT    NOT NULL,
            asin       TEXT    NOT NULL UNIQUE,
            name       TEXT,
            image_url  TEXT,
            currency   TEXT    DEFAULT '$',
            created_at TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS price_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            price      REAL    NOT NULL,
            checked_at TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/products", methods=["GET"])
def list_products():
    db = get_db()
    rows = db.execute("""
        SELECT
            p.*,
            latest.price   AS current_price,
            latest.checked_at AS last_checked,
            mn.min_price   AS lowest_price
        FROM products p
        LEFT JOIN (
            SELECT product_id, price, checked_at
            FROM price_history ph1
            WHERE id = (
                SELECT id FROM price_history
                WHERE product_id = ph1.product_id
                ORDER BY checked_at DESC LIMIT 1
            )
        ) latest ON latest.product_id = p.id
        LEFT JOIN (
            SELECT product_id, MIN(price) AS min_price
            FROM price_history
            GROUP BY product_id
        ) mn ON mn.product_id = p.id
        ORDER BY p.created_at DESC
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()

    clean_url, asin = normalize_url(url)
    if not asin:
        return jsonify({"error": "Not a valid Amazon product URL."}), 400

    db = get_db()
    if db.execute("SELECT 1 FROM products WHERE asin=?", (asin,)).fetchone():
        return jsonify({"error": "Already tracking this product."}), 409

    try:
        info = fetch_product(clean_url)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    cur = db.execute(
        "INSERT INTO products (url, asin, name, image_url, currency) VALUES (?,?,?,?,?)",
        (clean_url, asin, info["name"], info["image_url"], info["currency"]),
    )
    db.execute(
        "INSERT INTO price_history (product_id, price) VALUES (?,?)",
        (cur.lastrowid, info["price"]),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, **info}), 201


@app.route("/api/products/<int:pid>", methods=["DELETE"])
def delete_product(pid):
    db = get_db()
    db.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/products/<int:pid>/history")
def product_history(pid):
    db = get_db()
    rows = db.execute(
        "SELECT price, checked_at FROM price_history WHERE product_id=? ORDER BY checked_at",
        (pid,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/refresh", methods=["POST"])
def refresh_all():
    db = get_db()
    products = db.execute("SELECT id, url FROM products").fetchall()
    results = []
    for p in products:
        try:
            info = fetch_product(p["url"])
            db.execute(
                "INSERT INTO price_history (product_id, price) VALUES (?,?)",
                (p["id"], info["price"]),
            )
            db.execute(
                "UPDATE products SET name=?, image_url=?, currency=? WHERE id=?",
                (info["name"], info["image_url"], info["currency"], p["id"]),
            )
            results.append({"id": p["id"], "price": info["price"], "ok": True})
        except Exception as exc:
            results.append({"id": p["id"], "error": str(exc), "ok": False})
        time.sleep(2)
    db.commit()
    return jsonify(results)


# ---------------------------------------------------------------------------
# Background price refresh
# ---------------------------------------------------------------------------

def _background_loop():
    while True:
        time.sleep(REFRESH_INTERVAL_HOURS * 3600)
        conn = _connect()
        products = conn.execute("SELECT id, url FROM products").fetchall()
        for p in products:
            try:
                info = fetch_product(p["url"])
                conn.execute(
                    "INSERT INTO price_history (product_id, price) VALUES (?,?)",
                    (p["id"], info["price"]),
                )
                conn.execute(
                    "UPDATE products SET name=?, image_url=?, currency=? WHERE id=?",
                    (info["name"], info["image_url"], info["currency"], p["id"]),
                )
                conn.commit()
            except Exception:
                pass
            time.sleep(3)
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    threading.Thread(target=_background_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5001))
    print(f"\n  Amazon Price Tracker running at http://0.0.0.0:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
