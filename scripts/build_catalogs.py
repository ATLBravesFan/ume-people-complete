#!/usr/bin/env python3
"""Build static Stremio actor/director catalogs from TMDB for GitHub Pages.

- 59 actors: movie cast + TV cast credits
- 20 directors: movie crew credits whose job is exactly Director
- Reuses existing UME catalog IDs wherever possible
- Emits one complete static JSON response per catalog (no pagination required)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PEOPLE_FILE = ROOT / "people.json"
SITE = ROOT / "site"
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE = "https://image.tmdb.org/t/p"
VERSION = "5.0.0"
INCLUDE_SELF_APPEARANCES = False

API_KEY = os.environ.get("TMDB_API_KEY", "").strip()
if not API_KEY:
    raise SystemExit("TMDB_API_KEY is missing. Add it as a GitHub Actions repository secret.")


def norm(value: str | None) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", value or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[„“”\"'’`]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def is_self(character: str | None) -> bool:
    c = norm(character)
    if not c:
        return False
    return (
        c in {"self", "himself", "herself", "themselves"}
        or c.startswith("self ")
        or c.startswith("self -")
        or "archive footage" in c
    )


def tmdb_get(path: str, params: dict[str, Any] | None = None, retries: int = 4) -> dict[str, Any]:
    q = {"api_key": API_KEY, "language": "en-US"}
    if params:
        q.update(params)
    url = f"{TMDB_BASE}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "UME-People-GitHub-Pages/5.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt + 1 >= retries:
                raise RuntimeError(f"TMDB request failed: {path}: {e}") from e
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def resolve_person_id(search_name: str) -> int:
    data = tmdb_get("/search/person", {"query": search_name, "include_adult": "false", "page": 1})
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"TMDB person not found: {search_name}")
    target = norm(search_name)
    exact = [p for p in results if norm(p.get("name")) == target]
    pool = exact or results
    pool.sort(key=lambda p: float(p.get("popularity") or 0), reverse=True)
    return int(pool[0]["id"])


def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        if item.get("id") is None:
            continue
        k = str(item["id"])
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


def date_value(item: dict[str, Any], media_type: str) -> str:
    return (item.get("release_date") if media_type == "movie" else item.get("first_air_date")) or ""


def sort_credits(items: list[dict[str, Any]], media_type: str) -> list[dict[str, Any]]:
    # Popular titles first; every retained credit remains in the file.
    return sorted(items, key=lambda x: (float(x.get("popularity") or 0), date_value(x, media_type)), reverse=True)


def to_meta(item: dict[str, Any], media_type: str) -> dict[str, Any]:
    is_movie = media_type == "movie"
    title = item.get("title") if is_movie else item.get("name")
    date = item.get("release_date") if is_movie else item.get("first_air_date")
    year = date[:4] if isinstance(date, str) and re.match(r"^\d{4}", date) else None
    meta: dict[str, Any] = {
        "id": f"tmdb:{item['id']}",
        "type": media_type if media_type == "movie" else "series",
        "name": title or f"TMDB {item['id']}",
    }
    if item.get("poster_path"):
        meta["poster"] = f"{TMDB_IMAGE}/w500{item['poster_path']}"
    if item.get("backdrop_path"):
        meta["background"] = f"{TMDB_IMAGE}/w780{item['backdrop_path']}"
    if item.get("overview"):
        meta["description"] = item["overview"]
    if year:
        meta["releaseInfo"] = year
        meta["year"] = int(year)
    return meta


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    people = json.loads(PEOPLE_FILE.read_text(encoding="utf-8"))
    actors = people["actors"]
    directors = people["directors"]

    if SITE.exists():
        import shutil
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    catalogs: list[dict[str, Any]] = []
    report: dict[str, Any] = {"version": VERSION, "actors": {}, "directors": {}, "errors": []}

    # Resolve each unique person once.
    person_ids: dict[str, int] = {}
    for entry in [*actors, *directors]:
        search_name = entry.get("searchName") or entry["name"]
        if search_name not in person_ids:
            person_ids[search_name] = resolve_person_id(search_name)
            time.sleep(0.05)

    for actor in actors:
        name = actor["name"]
        pid = person_ids[actor.get("searchName") or name]
        movie_data = tmdb_get(f"/person/{pid}/movie_credits")
        tv_data = tmdb_get(f"/person/{pid}/tv_credits")

        movies = movie_data.get("cast") or []
        shows = tv_data.get("cast") or []
        if not INCLUDE_SELF_APPEARANCES:
            movies = [x for x in movies if not is_self(x.get("character"))]
            shows = [x for x in shows if not is_self(x.get("character"))]
        movies = sort_credits(dedupe(movies), "movie")
        shows = sort_credits(dedupe(shows), "series")

        movie_id = actor["movieCatalogId"]
        show_id = actor["showCatalogId"]
        movie_name = f"[Actors] {name} (Movies)"
        show_name = f"[Actors] {name} (Shows)"
        catalogs += [
            {"type": "movie", "id": movie_id, "name": movie_name},
            {"type": "series", "id": show_id, "name": show_name},
        ]
        write_json(SITE / "catalog" / "movie" / f"{movie_id}.json", {"metas": [to_meta(x, "movie") for x in movies]})
        write_json(SITE / "catalog" / "series" / f"{show_id}.json", {"metas": [to_meta(x, "series") for x in shows]})
        report["actors"][name] = {"tmdbPersonId": pid, "movieCount": len(movies), "showCount": len(shows)}
        print(f"Actor: {name}: {len(movies)} movies, {len(shows)} shows")
        time.sleep(0.05)

    for director in directors:
        name = director["name"]
        pid = person_ids[director.get("searchName") or name]
        movie_data = tmdb_get(f"/person/{pid}/movie_credits")
        crew = movie_data.get("crew") or []
        movies = [x for x in crew if x.get("job") == "Director" and (not x.get("department") or x.get("department") == "Directing")]
        movies = sort_credits(dedupe(movies), "movie")

        catalog_id = director["movieCatalogId"]
        catalog_name = f"[Directors] {name} (Movies)"
        catalogs.append({"type": "movie", "id": catalog_id, "name": catalog_name})
        write_json(SITE / "catalog" / "movie" / f"{catalog_id}.json", {"metas": [to_meta(x, "movie") for x in movies]})
        report["directors"][name] = {"tmdbPersonId": pid, "movieCount": len(movies)}
        print(f"Director: {name}: {len(movies)} directed movies")
        time.sleep(0.05)

    manifest = {
        "id": "com.ume.people.complete.github.v5",
        "version": VERSION,
        "name": "UME People Complete - GitHub",
        "description": "Complete TMDB actor movie/TV cast credits and exact Director-job movie credits for Strand/AIOMetadata.",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": catalogs,
        "behaviorHints": {"adult": False, "configurable": False},
    }
    write_json(SITE / "manifest.json", manifest)
    write_json(SITE / "health.json", {
        "status": "ok",
        "version": VERSION,
        "actors": len(actors),
        "directors": len(directors),
        "catalogs": len(catalogs),
    })
    write_json(SITE / "build-report.json", report)

    expected = len(actors) * 2 + len(directors)
    if len(catalogs) != expected or expected != 138:
        raise RuntimeError(f"Catalog count mismatch: generated {len(catalogs)}, expected {expected} / 138")

    print(f"SUCCESS: generated {len(catalogs)} catalogs")


if __name__ == "__main__":
    main()
