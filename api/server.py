"""AI Freelance Swarm API server (stdlib only)."""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_WORKFLOW = DATA_DIR / "workflow.db"
DB_TRACKING = DATA_DIR / "tracking.db"
DB_ALLOCATION = DATA_DIR / "allocation.db"
README_PATH = ROOT / "README.md"
PORT = 4123
HOST = "127.0.0.1"


def init_dbs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    schemas = {
        DB_WORKFLOW: (ROOT / "orchestration" / "schema.sql").read_text(),
        DB_TRACKING: (ROOT / "tracking" / "schema.sql").read_text(),
        DB_ALLOCATION: (ROOT / "allocation" / "schema.sql").read_text(),
    }
    for db, sql in schemas.items():
        if not db.exists():
            with sqlite3.connect(db) as conn:
                conn.executescript(sql)
                conn.commit()


def db_execute(db: Path, sql: str, params: tuple | list = ()) -> list[tuple]:
    with sqlite3.connect(db) as conn:
        cursor = conn.execute(sql, params)
        return cursor.fetchall()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass

    def _send_json(self, code: int, obj) -> None:
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        return json.loads(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(b"")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path in ("/", ""):
            md = README_PATH.read_text() if README_PATH.exists() else "# AI Freelance Swarm\n"
            payload = md.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/api/health":
            return self._send_json(200, {"status": "ok", "ts": __import__("datetime").datetime.now().isoformat()})

        if path == "/api/runs":
            rows = db_execute(DB_WORKFLOW, "SELECT id, status, current_agent, current_step, total_steps, updated_at FROM workflow_runs ORDER BY created_at DESC")
            data = [
                {"id": r[0], "status": r[1], "current_agent": r[2], "current_step": r[3], "total_steps": r[4], "updated_at": r[5]}
                for r in rows
            ]
            return self._send_json(200, data)

        if path.startswith("/api/runs/"):
            run_id = path.split("/")[3]
            rows = db_execute(DB_WORKFLOW, "SELECT id, status, current_agent, current_step, total_steps, created_at, updated_at, finished_at, metadata FROM workflow_runs WHERE id = ?", (run_id,))
            if not rows:
                return self._send_json(404, {"error": "not found"})
            r = rows[0]
            return self._send_json(200, {"id": r[0], "status": r[1], "current_agent": r[2], "current_step": r[3], "total_steps": r[4], "created_at": r[5], "updated_at": r[6], "finished_at": r[7], "metadata": json.loads(r[8] or "{}")})

        if path == "/api/tokens/totals":
            run_id = qs.get("project", [None])[0]
            if run_id:
                rows = db_execute(DB_TRACKING, "SELECT COALESCE(SUM(est_cost_usd),0) FROM token_usages WHERE run_id = ?", (run_id,))
            else:
                rows = db_execute(DB_TRACKING, "SELECT COALESCE(SUM(est_cost_usd),0) FROM token_usages")
            total = float(rows[0][0] or 0.0)
            return self._send_json(200, {"run_id": run_id, "total_cost_usd": total})

        if path == "/api/tokens/budgets":
            rows = db_execute(DB_TRACKING, "SELECT agent_id, budget_per_run, max_consecutive_runs, updated_at FROM agent_budgets ORDER BY agent_id")
            data = [{"agent_id": r[0], "budget_per_run": r[1], "max_consecutive_runs": r[2], "updated_at": r[3]} for r in rows]
            return self._send_json(200, data)

        if path == "/api/allocation/rules":
            p = DATA_DIR / "allocation_rules.json"
            if p.exists():
                return self._send_json(200, json.loads(p.read_text()))
            return self._send_json(200, {"owner_payout_pct": 0.6, "ai_reinvestment_pct": 0.25, "emergency_reserve_pct": 0.15})

        if path == "/api/allocation/history":
            rows = db_execute(DB_ALLOCATION, "SELECT id, year, month, owner_payout_usd, ai_reinvestment_usd, emergency_reserve_usd, rules_snapshot, created_at FROM monthly_allocations ORDER BY year DESC, month DESC")
            data = [{"id": r[0], "year": r[1], "month": r[2], "owner_payout_usd": r[3], "ai_reinvestment_usd": r[4], "emergency_reserve_usd": r[5], "rules": json.loads(r[6]), "created_at": r[7]} for r in rows]
            return self._send_json(200, data)

        return self._send_json(404, {"error": "not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path == "/api/runs":
            run_id = body.get("run_id") or ("run-" + __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S"))
            now = __import__("datetime").datetime.now().isoformat()
            db_execute(
                DB_WORKFLOW,
                "INSERT OR REPLACE INTO workflow_runs (id, status, current_agent, current_step, total_steps, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "running", None, 0, body.get("total_steps", 5), now, now, json.dumps(body.get("metadata") or {})),
            )
            return self._send_json(201, {"id": run_id, "status": "running"})

        if path.startswith("/api/runs/") and path.count("/") == 3 and not path.endswith("/complete"):
            run_id = path.split("/")[3]
            return self._send_json(200, {"id": run_id, "note": "GET /api/runs/<id> for details"})

        if path.startswith("/api/runs/") and path.endswith("/complete") and path.count("/") == 4:
            run_id = path.split("/")[3]
            rows = db_execute(DB_WORKFLOW, "SELECT id, status, current_step, total_steps FROM workflow_runs WHERE id = ?", (run_id,))
            if not rows:
                return self._send_json(404, {"error": "not found", "run_id": run_id})
            _, _, cur, total = rows[0]
            nxt = min(cur + 1, total)
            now = __import__("datetime").datetime.now().isoformat()
            agent = body.get("agent_id")
            payload = json.dumps(body.get("payload") or {})
            db_execute(
                DB_WORKFLOW,
                "UPDATE workflow_runs SET current_step=?, current_agent=?, updated_at=? WHERE id=?",
                (nxt, agent, now, run_id),
            )
            db_execute(
                DB_WORKFLOW,
                "INSERT INTO workflow_events (run_id, ts, agent_id, event_type, payload) VALUES (?, ?, ?, ?, ?)",
                (run_id, now, agent or "system", "agent_completed", payload),
            )
            return self._send_json(200, {"run_id": run_id, "current_step": nxt, "total_steps": total})

        if path == "/api/tokens/usage":
            now = __import__("datetime").datetime.now().isoformat()
            run_id = body.get("run_id") or "run-local"
            agent_id = body.get("agent_id") or ""
            prompt_tokens = max(0, int(body.get("prompt_tokens") or 0))
            completion_tokens = max(0, int(body.get("completion_tokens") or 0))
            total = prompt_tokens + completion_tokens
            cost = max(0.0, float(body.get("est_cost_usd") or 0.0))
            model = body.get("model") or ""
            db_execute(
                DB_TRACKING,
                "INSERT INTO token_usages (ts, run_id, agent_id, prompt_tokens, completion_tokens, total_tokens, est_cost_usd, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (now, run_id, agent_id, prompt_tokens, completion_tokens, total, cost, model),
            )
            return self._send_json(201, {"recorded": True})

        return self._send_json(404, {"error": "not found", "path": path})

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path == "/api/allocation/rules":
            p = DATA_DIR / "allocation_rules.json"
            p.write_text(json.dumps(body, indent=2))
            return self._send_json(200, {"saved": True, "path": str(p)})

        return self._send_json(404, {"error": "not found", "path": path})


def main() -> None:
    init_dbs()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"AI Freelance Swarm API on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
