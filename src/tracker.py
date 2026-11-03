"""Job tracking: CSV (zero setup) or Google Sheets (gspread).

Both backends expose the same `upsert(job)` interface so the pipeline does not
care where rows live.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Any

from .config import Config
from .utils import ensure_dir, log

DEFAULT_COLUMNS = [
    "asin", "status", "product_title", "brand",
    "base_images_found", "slots_done", "bundle_path", "error", "updated_at",
]


class Tracker:
    columns: list[str] = DEFAULT_COLUMNS

    def upsert(self, job: dict[str, Any]) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def _row(self, job: dict[str, Any]) -> list[str]:
        job = {**job, "updated_at": job.get("updated_at") or dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        return [str(job.get(c, "")) for c in self.columns]


class CsvTracker(Tracker):
    def __init__(self, path: str | Path, columns: list[str] | None = None):
        self.path = Path(path)
        self.columns = columns or DEFAULT_COLUMNS
        ensure_dir(self.path.parent)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(self.columns)

    def upsert(self, job: dict[str, Any]) -> None:
        rows: list[list[str]] = []
        with self.path.open("r", newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        header = rows[0] if rows else list(self.columns)
        body = [r for r in rows[1:] if r and r[0] != job.get("asin")]
        body.append(self._row(job))
        with self.path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(body)


class SheetsTracker(Tracker):
    def __init__(self, cfg: Config):
        import gspread
        from google.oauth2.service_account import Credentials

        self.cfg = cfg
        self.columns = cfg.get("sheet.columns", DEFAULT_COLUMNS) or DEFAULT_COLUMNS
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds_file = cfg.get("sheet.credentials_file")
        creds_path = cfg.resolve(creds_file) if creds_file else None
        if creds_path and creds_path.exists():
            creds = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(  # env var path
                __import__("os").environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=scopes
            )
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(cfg.get("sheet.spreadsheet_id")).worksheet(
            cfg.get("sheet.worksheet_name", "ASIN Jobs")
        )
        self._ensure_header()

    def _ensure_header(self) -> None:
        first_row = self.sheet.row_values(1)
        if not first_row or first_row[0] != self.columns[0]:
            self.sheet.update("A1", [self.columns])

    def upsert(self, job: dict[str, Any]) -> None:
        col_a = self.sheet.col_values(1)
        row = self._row(job)
        try:
            idx = col_a.index(job["asin"]) + 1
        except ValueError:
            idx = len(col_a) + 1
        self.sheet.update(f"A{idx}:{chr(64 + len(self.columns))}{idx}", [row])


def build_tracker(cfg: Config) -> Tracker:
    if not cfg.get("sheet.enabled", True):
        return CsvTracker(cfg.resolve(cfg.get("sheet.csv_path", "data/tracking.csv")))
    backend = (cfg.get("sheet.backend", "csv") or "csv").lower()
    if backend == "gspread":
        try:
            tracker = SheetsTracker(cfg)
            log.info("tracking -> Google Sheet %s", cfg.get("sheet.spreadsheet_id"))
            return tracker
        except Exception as exc:  # noqa: BLE001
            log.error("Sheets unavailable (%s) - falling back to CSV", exc)
    return CsvTracker(
        cfg.resolve(cfg.get("sheet.csv_path", "data/tracking.csv")),
        cfg.get("sheet.columns", DEFAULT_COLUMNS),
    )
