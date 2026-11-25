"""Region sources: each yields named lon/lat outlines.

A source knows where to download its data and how to turn records into `Region`s.
Adding countries later means adding another source here; the geometry and asset
code does not change.
"""
from __future__ import annotations

import re
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import shapefile  # pyshp
from shapely.geometry import shape

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Region:
    key: str  # short stable id, used in node identifiers and file names
    name: str  # display name
    geometry: object  # shapely (Multi)Polygon in lon/lat degrees
    group: str = ""  # key of the Group this region belongs to
    info: dict = field(default_factory=dict)


@dataclass
class Group:
    """One asset's worth of regions. Groups of a source never overlap, so any
    combination of group assets can be loaded together."""

    key: str  # identifier-safe, also the asset file name (lower case)
    name: str  # e.g. "Northeast States"


@dataclass
class Source:
    key: str  # used in identifiers: Scale_<key>_<region>
    title: str  # GUI folder name, e.g. "US States"
    url: str
    filename: str
    attribution: str
    groups: list[Group] = field(default_factory=list)
    folder: str = ""  # output folder and set asset name, e.g. "us_states"
    license: str = ""  # terms of the boundary data, for LICENSE.md
    style_overrides: dict = field(default_factory=dict)  # Style fields for this set

    def path(self) -> Path:
        p = DATA_DIR / self.filename
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            print(f"Downloading {self.url}")
            urllib.request.urlretrieve(self.url, p)
        return p

    def regions(self) -> list[Region]:
        raise NotImplementedError


def identifier_safe(text: str) -> str:
    """'New York' -> 'NewYork', 'Côte d'Ivoire' -> 'CoteDIvoire' (scene graph identifiers
    can't have spaces or dots; accents are dropped)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]", "", ascii_text.title())


# Common-usage regions (not the Census regions, which put e.g. Texas in the South).
# Every state is in exactly one group.
US_STATE_GROUPS = {
    ("Northeast", "Northeast States"): "ME NH VT MA RI CT NY NJ PA DE MD",
    ("Southeast", "Southeast States"): "VA WV NC SC GA FL KY TN AL MS AR LA",
    ("Midwest", "Midwest States"): "OH IN IL MI WI MN IA MO ND SD NE KS",
    ("Southwest", "Southwest States"): "AZ NM TX OK",
    ("West", "Western States"): "CO WY MT ID UT NV CA OR WA AK HI",
}
US_STATE_GROUP_OF = {
    code: key for (key, _), codes in US_STATE_GROUPS.items() for code in codes.split()
}
assert len(US_STATE_GROUP_OF) == 50


class USStates(Source):
    def __init__(self):
        super().__init__(
            key="US",
            title="US States",
            url="https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_5m.zip",
            filename="cb_2024_us_state_5m.zip",
            attribution="US Census Bureau, 2024 Cartographic Boundary Files (1:5,000,000)",
            groups=[Group(key, name) for key, name in US_STATE_GROUPS],
            folder="us_states",
            license=(
                "Public domain. The Cartographic Boundary Files are a work of the US "
                "Government (US Census Bureau) and not subject to copyright in the US "
                "(17 U.S.C. 105). https://www.census.gov/geographies/mapping-files.html"
            ),
        )

    def regions(self) -> list[Region]:
        out = []
        with shapefile.Reader(str(self.path())) as r:
            for sr in r.iterShapeRecords():
                rec = sr.record.as_dict()
                if rec["STUSPS"] not in US_STATE_GROUP_OF:  # DC, PR, territories
                    continue
                out.append(
                    Region(
                        key=identifier_safe(rec["NAME"]),
                        name=rec["NAME"],
                        geometry=shape(sr.shape.__geo_interface__),
                        group=US_STATE_GROUP_OF[rec["STUSPS"]],
                        info={
                            "abbreviation": rec["STUSPS"],
                            "land_km2": rec["ALAND"] / 1e6,
                            "water_km2": rec["AWATER"] / 1e6,
                        },
                    )
                )
        return sorted(out, key=lambda reg: reg.name)


# UN M49 subregions, in the order of the GUI and the set asset. Natural Earth's
# SUBREGION field follows them, except for its "Seven seas (open ocean)" catch-all.
COUNTRY_GROUPS = [
    "Northern America", "Central America", "Caribbean", "South America",
    "Northern Europe", "Western Europe", "Southern Europe", "Eastern Europe",
    "Northern Africa", "Western Africa", "Middle Africa", "Eastern Africa",
    "Southern Africa", "Western Asia", "Central Asia", "Southern Asia", "Eastern Asia",
    "South-Eastern Asia", "Australia and New Zealand", "Melanesia", "Micronesia",
    "Polynesia", "Antarctica",
]
COUNTRY_SUBREGION_FIXES = {  # Natural Earth NAME -> M49 subregion
    "Br. Indian Ocean Ter.": "Eastern Africa",
    "Fr. S. Antarctic Lands": "Eastern Africa",
    "Heard I. and McDonald Is.": "Australia and New Zealand",
    "Indian Ocean Ter.": "Australia and New Zealand",
    "S. Geo. and the Is.": "South America",
}
# Specks, leases, military bases, buffer zones and unclaimed or contested slivers: not
# places anyone would compare sizes with.
COUNTRY_EXCLUDE = {
    "Akrotiri", "Ashmore and Cartier Is.", "Baikonur", "Bajo Nuevo Bank", "Bir Tawil",
    "Brazilian I.", "Clipperton I.", "Coral Sea Is.", "Cyprus U.N. Buffer Zone",
    "Dhekelia", "Scarborough Reef", "Serranilla Bank", "Siachen Glacier",
    "Southern Patagonian Ice Field", "Spratly Is.", "U.S. Minor Outlying Is.",
    "USNB Guantanamo Bay",
}
# Display names: Natural Earth's NAME, or NAME_LONG where NAME is abbreviated
# ("Dem. Rep. Congo"), with these fixes.
COUNTRY_NAMES = {
    "Congo": "Republic of the Congo",
    "eSwatini": "Eswatini",
    "Micronesia": "Federated States of Micronesia",
    "St-Martin": "Saint Martin",
    "St-Barthélemy": "Saint Barthélemy",
    "Falkland Is.": "Falkland Islands",
    "Heard I. and McDonald Is.": "Heard Island and McDonald Islands",
}
# Parts of a country farther than this from the rest (chained, so island arcs stay
# together) are left out: France without French Guiana, the US without Hawaii.
COUNTRY_MAX_GAP_KM = 1000.0


class Countries(Source):
    def __init__(self):
        super().__init__(
            key="Country",
            title="Countries",
            url="https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
            filename="ne_10m_admin_0_countries.zip",
            attribution="Natural Earth, Admin 0 - Countries (1:10m), public domain",
            groups=[Group(_snake(n), n) for n in COUNTRY_GROUPS],
            folder="countries",
            license=(
                "Public domain. \"Made with Natural Earth. Free vector and raster map data "
                "@ naturalearthdata.com.\" https://www.naturalearthdata.com/about/terms-of-use/ "
                "Boundaries show de facto control as mapped by Natural Earth; they are not an "
                "endorsement of any claim."
            ),
        )

    def regions(self) -> list[Region]:
        from .geometry import drop_far_parts

        group_of = {g.name: g.key for g in self.groups}
        out = []
        with shapefile.Reader(str(self.path()), encoding="utf-8") as r:
            for sr in r.iterShapeRecords():
                rec = sr.record.as_dict()
                ne_name = rec["NAME"]
                if ne_name in COUNTRY_EXCLUDE:
                    continue
                name = COUNTRY_NAMES.get(
                    ne_name, rec["NAME_LONG"] if "." in ne_name else ne_name
                )
                subregion = COUNTRY_SUBREGION_FIXES.get(ne_name, rec["SUBREGION"])
                geometry, dropped = drop_far_parts(
                    shape(sr.shape.__geo_interface__), COUNTRY_MAX_GAP_KM
                )
                out.append(
                    Region(
                        key=identifier_safe(name),
                        name=name,
                        geometry=geometry,
                        group=group_of[subregion],
                        info={
                            "abbreviation": rec["ISO_A3_EH"] if rec["ISO_A3_EH"] != "-99" else "",
                            "type": rec["TYPE"],
                            "dropped_km2": dropped,
                        },
                    )
                )
        keys = [r.key for r in out]
        assert len(keys) == len(set(keys)), "duplicate country keys"
        return sorted(out, key=lambda reg: reg.name)


def _snake(text: str) -> str:
    """'South-Eastern Asia' -> 'south_eastern_asia'."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# --------------------------------------------------------------------------------------
# Cities
# --------------------------------------------------------------------------------------
# Cities are tens of km across: 10 km grid lines, a thin border band and a lighter border
# simplification than states and countries.
CITY_STYLE = {
    "grid_spacing": 10_000.0,
    "grid_width": 200.0,
    "outline_min": 250.0,
    "outline_max": 1_000.0,
    "simplify": 50.0,
}

GHS_UCDB_URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_UCDB_GLOBE_R2024A/"
    "GHS_UCDB_GLOBE_R2024A/V1-2/GHS_UCDB_GLOBE_R2024A_V1_2.zip"
)
GHS_UCDB_ATTRIBUTION = (
    "European Commission, Joint Research Centre: GHS Urban Centre Database 2025 "
    "(GHS-UCDB R2024A V1.2), doi:10.2905/1a338be6-7eaf-480c-9664-3a8ade88cbcd"
)
GHS_UCDB_LICENSE = (
    "CC BY 4.0, (c) European Union, 1995-2026 (https://creativecommons.org/licenses/by/4.0/). "
    "Changes: urban centre outlines reprojected from Mollweide to longitude/latitude, "
    "simplified by 50 m and turned into 3D models; populations quoted in descriptions."
)
GHS_TABLE = "GHSL_UCDB_THEME_GENERAL_CHARACTERISTICS_GLOBE_R2024A"
MOLLWEIDE_R = 6_378_137.0  # ESRI:54009 on WGS84: the sphere has the semi-major axis


def _mollweide_to_lonlat(geom):
    import numpy as np
    import shapely

    def fn(c):
        theta = np.arcsin(np.clip(c[:, 1] / (MOLLWEIDE_R * np.sqrt(2)), -1, 1))
        lat = np.degrees(np.arcsin((2 * theta + np.sin(2 * theta)) / np.pi))
        lon = np.degrees(np.pi * c[:, 0] / (2 * np.sqrt(2) * MOLLWEIDE_R * np.cos(theta)))
        return np.column_stack([lon, lat])

    return shapely.transform(geom, fn)


def _fix_mojibake(text: str) -> str:
    """Some GHS-UCDB names are UTF-8 read as Latin-1 ("CÃ´te d'Ivoire"); undo that."""
    if text and ("Ã" in text or "Â" in text):
        try:
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def _gpkg_geometry(blob: bytes):
    """GeoPackage geometry blob -> shapely (header + optional envelope + WKB)."""
    import shapely

    envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(blob[3] >> 1) & 7]
    return shapely.from_wkb(bytes(blob[8 + envelope:]))


class GHSUrbanCentres(Source):
    """Base for sets drawn from GHS-UCDB urban centres (one definition worldwide:
    contiguous 1 km cells of >= 1500 people/km2 totalling >= 50,000 people)."""

    def gpkg(self) -> Path:
        import zipfile

        out = self.path().parent / "GHS_UCDB_GLOBE_R2024A.gpkg"
        if not out.exists():
            print(f"Extracting {out.name}")
            zipfile.ZipFile(self.path()).extract(out.name, out.parent)
        return out

    def centres(self) -> list[dict]:
        import sqlite3

        con = sqlite3.connect(self.gpkg())
        cols = ["geom", "ID_UC_G0", "GC_UCN_MAI_2025", "GC_CNT_GAD_2025", "GC_POP_TOT_2025",
                "GC_UCM_CAP", "GC_DEV_USR_2025"]
        rows = con.execute(f'select {", ".join(cols)} from "{GHS_TABLE}"').fetchall()
        con.close()
        out = [dict(zip(cols, r)) for r in rows]
        for c in out:
            for k in ("GC_UCN_MAI_2025", "GC_CNT_GAD_2025"):
                c[k] = _fix_mojibake(c[k])
        return out

    def make_regions(self, centres: list[dict], group_of, note_of) -> list[Region]:
        out = []
        names = [c["GC_UCN_MAI_2025"] for c in centres]
        for c in centres:
            name = c["GC_UCN_MAI_2025"]
            key = identifier_safe(name)
            if names.count(name) > 1:
                key += identifier_safe(c["GC_CNT_GAD_2025"])
            out.append(Region(
                key=key,
                name=f'{name}, {c["GC_CNT_GAD_2025"]}',
                geometry=_mollweide_to_lonlat(_gpkg_geometry(c["geom"])),
                group=group_of(c),
                info={"note": note_of(c), "abbreviation": name,
                      "population": c["GC_POP_TOT_2025"]},
            ))
        keys = [r.key for r in out]
        assert len(keys) == len(set(keys)), "duplicate city keys"
        return out


def _population_note(c: dict) -> str:
    return (
        f'Urban centre population {c["GC_POP_TOT_2025"]:,.0f} (2025, GHS-UCDB; the '
        "contiguous dense area, which can span several named cities)."
    )


# UN SDG regions (GHS-UCDB's GC_DEV_USR_2025), Oceania merged with Australia/NZ.
CAPITAL_GROUPS = {
    "Northern America": "Northern America",
    "Latin America and the Caribbean": "Latin America and the Caribbean",
    "Europe": "Europe",
    "Northern Africa and Western Asia": "Northern Africa and Western Asia",
    "Sub-Saharan Africa": "Sub-Saharan Africa",
    "Central and Southern Asia": "Central and Southern Asia",
    "Eastern and South-Eastern Asia": "Eastern and South-Eastern Asia",
    "Australia and New Zealand": "Oceania",
    "Oceania": "Oceania",
}


class CountryCapitals(GHSUrbanCentres):
    def __init__(self):
        names = list(dict.fromkeys(CAPITAL_GROUPS.values()))
        super().__init__(
            key="Capital",
            title="Country Capitals",
            url=GHS_UCDB_URL,
            filename="ghs_ucdb/GHS_UCDB_GLOBE_R2024A_V1_2.zip",
            attribution=GHS_UCDB_ATTRIBUTION,
            groups=[Group(_snake(n) + "_capitals", n + " Capitals") for n in names],
            folder="country_capitals",
            license=GHS_UCDB_LICENSE + (
                " Capitals are the urban centres GHS-UCDB flags as capitals (GC_UCM_CAP); "
                "capitals under 50,000 people have no urban centre and are not included."
            ),
            style_overrides=CITY_STYLE,
        )

    def regions(self) -> list[Region]:
        caps = [c for c in self.centres() if c["GC_UCM_CAP"] == 1]
        regions = self.make_regions(
            caps,
            group_of=lambda c: _snake(CAPITAL_GROUPS[c["GC_DEV_USR_2025"]]) + "_capitals",
            note_of=_population_note,
        )
        return sorted(regions, key=lambda r: r.name)


class MostPopulatedCities(GHSUrbanCentres):
    COUNT = 100

    def __init__(self):
        super().__init__(
            key="TopCity",
            title="100 Most Populated Cities",
            url=GHS_UCDB_URL,
            filename="ghs_ucdb/GHS_UCDB_GLOBE_R2024A_V1_2.zip",
            attribution=GHS_UCDB_ATTRIBUTION,
            groups=[Group(_snake(c), f"Most Populated Cities in {c}") for c in CONTINENTS],
            folder="most_populated_cities",
            license=GHS_UCDB_LICENSE + (
                " Ranked by GHS-UCDB 2025 urban centre population; continents from the "
                "Natural Earth country (public domain) containing each centre."
            ),
            style_overrides=CITY_STYLE,
        )

    def regions(self) -> list[Region]:
        top = sorted(self.centres(), key=lambda c: -(c["GC_POP_TOT_2025"] or 0))[: self.COUNT]
        rank = {c["ID_UC_G0"]: i + 1 for i, c in enumerate(top)}
        continent = _continent_lookup()
        return self.make_regions(  # kept in rank order
            top,
            group_of=lambda c: _snake(continent(_mollweide_to_lonlat(_gpkg_geometry(c["geom"])))),
            note_of=lambda c: f'Rank {rank[c["ID_UC_G0"]]} of {self.COUNT} worldwide. '
                              + _population_note(c),
        )


OPENSPACE_USAGE_URL = "https://status.openspaceproject.com/assets/usage-D_1U0_0U.json"


class TopOpenSpaceCities(GHSUrbanCentres):
    """The 50 urban centres where OpenSpace is launched most, from the usage statistics
    published at status.openspaceproject.com. Each launch location (lat/lng, ~100 m) is
    assigned to the GHS-UCDB urban centre containing it, else the nearest centre within
    NEAR_KM (suburbs and small towns around a city); the rest is not counted."""

    COUNT = 50
    NEAR_KM = 25.0

    def __init__(self):
        super().__init__(
            key="OSCity",
            title="Top OpenSpace Cities",
            url=GHS_UCDB_URL,
            filename="ghs_ucdb/GHS_UCDB_GLOBE_R2024A_V1_2.zip",
            attribution=GHS_UCDB_ATTRIBUTION,
            groups=[Group(_snake(c), f"Top OpenSpace Cities in {c}") for c in CONTINENTS],
            folder="top_openspace_cities",
            license=GHS_UCDB_LICENSE + (
                " Ranked by OpenSpace launch counts from the usage statistics at "
                "status.openspaceproject.com (aggregate counts per location, assigned to "
                "urban centres); continents from the Natural Earth country (public domain) "
                "containing each centre."
            ),
            style_overrides=CITY_STYLE,
        )

    def usage_path(self) -> Path:
        p = DATA_DIR / "openspace_usage.json"
        if not p.exists():
            print(f"Downloading {OPENSPACE_USAGE_URL}")
            urllib.request.urlretrieve(OPENSPACE_USAGE_URL, p)
        return p

    def launches(self, centres: list[dict], geoms: list) -> tuple[dict, dict]:
        """Returns ({centre index: launches}, summary counts)."""
        import json
        import math

        import numpy as np
        import shapely

        data = json.loads(self.usage_path().read_text(encoding="utf-8"))
        places = [(p["lng"], p["lat"], sum(p["months"][1::2])) for p in data["places"]]
        pts = shapely.points([(x, y) for x, y, _ in places])
        tree = shapely.STRtree(geoms)
        counts: dict[int, int] = {}
        total = inside = near = 0
        hit_pt, hit_c = tree.query(pts, predicate="within")
        assigned = {}
        for pi, ci in zip(hit_pt, hit_c):
            assigned.setdefault(int(pi), int(ci))  # centres don't overlap
        for i, (lng, lat, n) in enumerate(places):
            total += n
            ci = assigned.get(i)
            if ci is not None:
                inside += n
            else:
                c, d = tree.query_nearest(pts[i], return_distance=True, all_matches=False)
                km = float(d[0]) * 111.2 * max(0.2, math.cos(math.radians(lat)))
                if km > self.NEAR_KM:
                    continue
                ci = int(c[1]) if getattr(c, "ndim", 1) == 2 else int(c[0])
                near += n
            counts[ci] = counts.get(ci, 0) + n
        return counts, {"total": total, "inside": inside, "near": near}

    def regions(self) -> list[Region]:
        centres = self.centres()
        geoms = [_mollweide_to_lonlat(_gpkg_geometry(c["geom"])) for c in centres]
        counts, summary = self.launches(centres, geoms)
        order = sorted(counts, key=lambda i: -counts[i])[: self.COUNT]
        shown = sum(counts[i] for i in order)
        print(f'Launches: {summary["total"]:,}; in an urban centre {summary["inside"]:,}, '
              f'within {self.NEAR_KM:.0f} km {summary["near"]:,}; top {self.COUNT} '
              f'cover {shown:,} ({shown / summary["total"]:.0%})')
        top = [centres[i] for i in order]
        launches = {centres[i]["ID_UC_G0"]: counts[i] for i in order}
        rank = {c["ID_UC_G0"]: r + 1 for r, c in enumerate(top)}
        continent = _continent_lookup()
        return self.make_regions(
            top,
            group_of=lambda c: _snake(continent(_mollweide_to_lonlat(_gpkg_geometry(c["geom"])))),
            note_of=lambda c: (
                f'Rank {rank[c["ID_UC_G0"]]} of {self.COUNT} OpenSpace cities: '
                f'{launches[c["ID_UC_G0"]]:,} launches (OpenSpace usage statistics, all time, '
                f'launches within or up to {self.NEAR_KM:.0f} km of the urban centre). '
                + _population_note(c)
            ),
        )


CONTINENTS = ["Asia", "Africa", "Europe", "North America", "South America", "Oceania"]


def _continent_lookup():
    """Returns geometry -> continent, from the Natural Earth country containing (or,
    on a coast, nearest to) the geometry's representative point."""
    import shapely

    countries = Countries()
    with shapefile.Reader(str(countries.path()), encoding="utf-8") as r:
        geoms, conts = [], []
        for sr in r.iterShapeRecords():
            cont = sr.record["CONTINENT"]
            if cont == "Seven seas (open ocean)":
                continue
            geoms.append(shape(sr.shape.__geo_interface__))
            conts.append(cont)
    tree = shapely.STRtree(geoms)

    def lookup(geom) -> str:
        cont = conts[int(tree.nearest(geom.representative_point()))]
        assert cont in CONTINENTS, cont
        return cont

    return lookup


# State -> capital as named in the Census places file. Consolidated city-counties are
# stored as "<name> ... (balance)" there; the matcher accepts that.
US_STATE_CAPITALS = {
    "AL": "Montgomery", "AK": "Juneau", "AZ": "Phoenix", "AR": "Little Rock",
    "CA": "Sacramento", "CO": "Denver", "CT": "Hartford", "DE": "Dover",
    "FL": "Tallahassee", "GA": "Atlanta", "HI": "Urban Honolulu", "ID": "Boise City",
    "IL": "Springfield", "IN": "Indianapolis", "IA": "Des Moines", "KS": "Topeka",
    "KY": "Frankfort", "LA": "Baton Rouge", "ME": "Augusta", "MD": "Annapolis",
    "MA": "Boston", "MI": "Lansing", "MN": "St. Paul", "MS": "Jackson",
    "MO": "Jefferson City", "MT": "Helena", "NE": "Lincoln", "NV": "Carson City",
    "NH": "Concord", "NJ": "Trenton", "NM": "Santa Fe", "NY": "Albany",
    "NC": "Raleigh", "ND": "Bismarck", "OH": "Columbus", "OK": "Oklahoma City",
    "OR": "Salem", "PA": "Harrisburg", "RI": "Providence", "SC": "Columbia",
    "SD": "Pierre", "TN": "Nashville-Davidson", "TX": "Austin", "UT": "Salt Lake City",
    "VT": "Montpelier", "VA": "Richmond", "WA": "Olympia", "WV": "Charleston",
    "WI": "Madison", "WY": "Cheyenne",
}
US_CAPITAL_DISPLAY = {
    "Urban Honolulu": "Honolulu", "Boise City": "Boise", "Nashville-Davidson": "Nashville",
}


class USStateCapitals(Source):
    def __init__(self):
        super().__init__(
            key="USCapital",
            title="US State Capitals",
            url="https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_place_500k.zip",
            filename="cb_2024_us_place_500k.zip",
            attribution="US Census Bureau, 2024 Cartographic Boundary Files, Places (1:500,000)",
            groups=[Group(key.lower() + "_capitals", name.replace("States", "State Capitals"))
                    for key, name in US_STATE_GROUPS],
            folder="us_state_capitals",
            license=(
                "Public domain (work of the US Government, 17 U.S.C. 105). Outlines are "
                "official city limits (incorporated places and census designated places), "
                "not the built-up area. https://www.census.gov/geographies/mapping-files.html"
            ),
            style_overrides=CITY_STYLE,
        )

    def regions(self) -> list[Region]:
        found = {}
        with shapefile.Reader(str(self.path())) as r:
            for sr in r.iterShapeRecords():
                rec = sr.record.as_dict()
                cap = US_STATE_CAPITALS.get(rec["STUSPS"])
                if cap is None:
                    continue
                name = rec["NAME"]
                if name == cap or (name.startswith(cap) and name.endswith("(balance)")):
                    if rec["STUSPS"] in found:
                        raise ValueError(f"two matches for {cap}, {rec['STUSPS']}")
                    found[rec["STUSPS"]] = (rec, shape(sr.shape.__geo_interface__))
        missing = set(US_STATE_CAPITALS) - set(found)
        assert not missing, f"capitals not found: {sorted(missing)}"
        out = []
        for st, (rec, geom) in found.items():
            cap = US_STATE_CAPITALS[st]
            city = US_CAPITAL_DISPLAY.get(cap, cap)
            out.append(Region(
                key=identifier_safe(city),
                name=f'{city}, {rec["STATE_NAME"]}',
                geometry=geom,
                group=US_STATE_GROUP_OF[st].lower() + "_capitals",
                info={
                    "abbreviation": st,
                    "note": f'City limits of {rec["NAMELSAD"]}, land area '
                            f'{rec["ALAND"] / 1e6:,.0f} km².',
                },
            ))
        keys = [r.key for r in out]
        assert len(keys) == len(set(keys)), "duplicate capital keys"
        return sorted(out, key=lambda r: r.name)


SOURCES = {
    "us-states": USStates,
    "countries": Countries,
    "country-capitals": CountryCapitals,
    "most-populated-cities": MostPopulatedCities,
    "top-openspace-cities": TopOpenSpaceCities,
    "us-state-capitals": USStateCapitals,
}
