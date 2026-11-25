#!/usr/bin/env python3
"""Find and download NISAR GCOV granules over a point from NASA CMR / ASF DAAC.

Searching needs no login. Downloading needs an Earthdata Login bearer token,
read from the EARTHDATA_TOKEN environment variable or from the first line of
~/.earthdata_token (or --token-file). The token is never printed.

Example (Krasheninnikov volcano, descending track 060):
    python nisar_download.py data/krash --track 060 --direction D \
        --start 2025-12-01 --end 2026-09-01
Use --list to only print what would be downloaded.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Sequence

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
COLLECTIONS = (
    "NISAR_L2_GCOV_V1",
    "NISAR_L2_GCOV_BETA_V1",
    "NISAR_L2_GCOV_PROVISIONAL_V1",
)
DEFAULT_POINT = (160.27, 54.59)  # lon, lat: Krasheninnikov volcano


def search(point, start, end, track, direction) -> list[dict]:
    found: dict[str, dict] = {}
    for short_name in COLLECTIONS:
        query = urllib.parse.urlencode(
            {
                "short_name": short_name,
                "point": f"{point[0]},{point[1]}",
                "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
                "page_size": 200,
                "sort_key": "start_date",
            }
        )
        with urllib.request.urlopen(f"{CMR}?{query}", timeout=60) as response:
            entries = json.load(response)["feed"]["entry"]
        for entry in entries:
            title = entry["title"]
            parts = title.split("_")
            # NISAR_L2_PR_GCOV_<cycle>_<track>_<A|D>_...
            if track and parts[5] != track.zfill(3):
                continue
            if direction and parts[6] != direction:
                continue
            url = next(
                (
                    link["href"]
                    for link in entry["links"]
                    if link["href"].startswith("https://")
                    and link["href"].endswith(".h5")
                    and "data#" in link["rel"]
                ),
                None,
            )
            if url:
                found[title] = {
                    "title": title,
                    "url": url,
                    "size_mb": float(entry.get("granule_size", 0)),
                    "collection": short_name,
                }
    return sorted(found.values(), key=lambda g: g["title"].split("_")[-6])


def load_token(token_file: Path | None) -> str:
    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not token:
        path = token_file or Path.home() / ".earthdata_token"
        if path.exists():
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            token = lines[0].strip() if lines else ""
    if not token:
        sys.exit(
            "No Earthdata token found. Set EARTHDATA_TOKEN or put the token on "
            "the first line of ~/.earthdata_token."
        )
    return token


class _NoAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Drop the bearer token when a redirect leaves the original host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and (
            urllib.parse.urlparse(newurl).hostname
            != urllib.parse.urlparse(req.full_url).hostname
        ):
            new.headers.pop("Authorization", None)
            new.unredirected_hdrs.pop("Authorization", None)
        return new


def download(url: str, destination: Path, token: str) -> None:
    opener = urllib.request.build_opener(_NoAuthOnRedirect)
    part = destination.with_name(destination.name + ".part")
    offset = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    try:
        response = opener.open(request, timeout=120)
    except urllib.error.HTTPError as error:
        if error.code == 416 and offset:  # already complete
            part.replace(destination)
            return
        if error.code in (401, 403):
            sys.exit(f"Download refused (HTTP {error.code}): check the token is valid/unexpired.")
        raise
    mode = "ab" if offset and response.status == 206 else "wb"
    done = offset if mode == "ab" else 0
    total = done + int(response.headers.get("Content-Length", 0))
    with response, open(part, mode) as out:
        while chunk := response.read(8 * 1024 * 1024):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e9:5.2f} / {total / 1e9:.2f} GB", end="", flush=True)
    print()
    part.replace(destination)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--point", nargs=2, type=float, default=DEFAULT_POINT,
                        metavar=("LON", "LAT"))
    parser.add_argument("--start", default="2025-12-01")
    parser.add_argument("--end", default="2026-09-01")
    parser.add_argument("--track", help="e.g. 060")
    parser.add_argument("--direction", choices=("A", "D"))
    parser.add_argument("--list", action="store_true", help="only list matches")
    parser.add_argument("--token-file", type=Path)
    args = parser.parse_args(argv)

    granules = search(tuple(args.point), args.start, args.end, args.track, args.direction)
    total_gb = sum(g["size_mb"] for g in granules) / 1000
    print(f"{len(granules)} granules, about {total_gb:.1f} GB")
    for g in granules:
        print(f"  {g['title']}  ({g['size_mb'] / 1000:.1f} GB, {g['collection']})")
    if args.list or not granules:
        return 0

    token = load_token(args.token_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for g in granules:
        destination = args.output_dir / f"{g['title']}.h5"
        if destination.exists():
            print(f"have {destination.name}")
            continue
        print(f"downloading {destination.name}")
        download(g["url"], destination, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
