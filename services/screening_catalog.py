"""Group structural station modules and aliases with identical propagation inputs.

This is a catalog policy, not a distance/velocity filter or docking inference.
Re-evaluated on every run: independent elements restore visiting spacecraft.
Structural modules are explicitly mapped to their station.
"""
from math import isfinite

STATION_IDS = frozenset((25544, 48274))  # ISS Zarya and CSS Tianhe
# Structural modules, not visiting spacecraft. Never classify by name prefix.
MODULE_PARENTS = {36086: 25544, 49044: 25544, 53239: 48274, 54216: 48274}
POLICY = "station-components-v1"
DYNAMIC_FIELDS = (
    "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER", "MEAN_ANOMALY", "BSTAR",
    "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT",
)


def propagation_key(satellite):
    data = satellite.omm_data
    values = tuple(float(data[field]) for field in DYNAMIC_FIELDS)
    if not all(isfinite(value) for value in values):
        raise ValueError("Non-finite propagation input")
    # No rounding or tolerance: merely nearby orbits must remain independent.
    return (data["EPOCH"], *values)


def prepare_screening_catalog(satellites):
    satellites = list(satellites)
    if len({sat.norad_id for sat in satellites}) != len(satellites):
        raise ValueError("Duplicate NORAD IDs in screening catalog")
    present_ids = {sat.norad_id for sat in satellites}
    anchors = {}
    for sat in sorted(satellites, key=lambda item: item.norad_id):
        parent = MODULE_PARENTS.get(sat.norad_id, sat.norad_id)
        if parent in STATION_IDS and parent in present_ids:
            anchors.setdefault(propagation_key(sat), parent)
    representatives, aliases = [], []
    for sat in satellites:
        parent = MODULE_PARENTS.get(sat.norad_id)
        anchor = parent if parent in present_ids else anchors.get(propagation_key(sat))
        if anchor is not None and anchor != sat.norad_id and sat.norad_id not in STATION_IDS:
            aliases.append({"norad_id": sat.norad_id, "representative_norad_id": anchor,
                            "reason": "structural_module" if parent == anchor else "identical_elements"})
        else:
            representatives.append(sat)
    return representatives, sorted(aliases, key=lambda item: item["norad_id"])
