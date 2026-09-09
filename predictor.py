"""Finite-resolution close-approach screening in a closed time window.

Broad-phase completeness is conditional on the configured relative-speed bound.
Local refinement resolves minima visible on its sampling grid; it is not a
proof of completeness for arbitrarily fast/oscillatory trajectories.
"""
import math
from datetime import timedelta, timezone
from functools import lru_cache
from bisect import bisect_left, bisect_right

from scipy.optimize import minimize_scalar
from scipy.spatial import cKDTree
from conjunction import ConjunctionEvent

DEFAULT_REFINEMENT_STEP_SECONDS = 10.0
DEFAULT_MAX_RELATIVE_SPEED_KM_S = 20.0
TCA_TOLERANCE_SECONDS = 0.001


def _positive(value, name, allow_zero=False):
    if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
        raise ValueError(f"{name} must be finite and {'non-negative' if allow_zero else 'positive'}")


def _grid(start, end, step):
    """Include both exact bounds, even when the last interval is shorter."""
    count = math.ceil((end - start) / step)
    if count > 1_000_000:
        raise ValueError("Sampling grid exceeds one million intervals")
    return [start + i * step for i in range(count)] + [end]


def distance_between(pos1, pos2):
    return math.dist(pos1, pos2)


def relative_velocity(vel1, vel2):
    return math.dist(vel1, vel2)


def checked_state(satellite, jd, fr):
    position, velocity = satellite.state_at(jd, fr)
    if (len(position) != 3 or len(velocity) != 3 or
            not all(math.isfinite(v) for v in (*position, *velocity))):
        raise RuntimeError(f"Non-finite or invalid state for NORAD {satellite.norad_id}")
    return position, velocity


def screening_radius_km(threshold_km, timestep_seconds,
                        max_relative_velocity_km_s=DEFAULT_MAX_RELATIVE_SPEED_KM_S):
    _positive(threshold_km, "threshold_km", allow_zero=True)
    _positive(timestep_seconds, "timestep_seconds")
    _positive(max_relative_velocity_km_s, "max_relative_velocity_km_s")
    # Deliberately use a whole step, retaining margin at either edge.
    return threshold_km + max_relative_velocity_km_s * timestep_seconds


def candidate_pairs_at_time(satellites, jd, fr, screening_radius_km,
                            max_relative_velocity_km_s=None):
    if len(satellites) < 2:
        return set()
    states = [checked_state(satellite, jd, fr) for satellite in satellites]
    if max_relative_velocity_km_s is not None:
        fastest = sorted((math.sqrt(sum(v*v for v in velocity)) for _, velocity in states), reverse=True)
        if sum(fastest[:2]) > max_relative_velocity_km_s:
            raise RuntimeError("Configured relative-speed bound is too small for the sampled catalog")
    tree = cKDTree([position for position, _ in states])
    return {tuple(sorted((satellites[i].norad_id, satellites[j].norad_id)))
            for i, j in tree.query_pairs(r=screening_radius_km)}


def compress_minutes_to_windows(minutes, timestep_minutes=1):
    if not minutes:
        return []
    minutes = sorted(set(minutes))
    windows = []
    start = end = minutes[0]
    for minute in minutes[1:]:
        if minute - end <= timestep_minutes + 1e-9:
            end = minute
        else:
            windows.append((start, end))
            start = end = minute
    return windows + [(start, end)]


def find_candidate_pairs(satellites, jd, fr, threshold_km=50.0, minutes=1440,
                         timestep_minutes=1,
                         max_relative_velocity_km_s=DEFAULT_MAX_RELATIVE_SPEED_KM_S):
    _positive(minutes, "minutes")
    _positive(timestep_minutes, "timestep_minutes")
    radius = screening_radius_km(threshold_km, timestep_minutes * 60, max_relative_velocity_km_s)
    candidates = {}
    for minute in _grid(0, minutes, timestep_minutes):
        for pair in candidate_pairs_at_time(satellites, jd, fr + minute / 1440.,
                                             radius, max_relative_velocity_km_s):
            candidates.setdefault(pair, []).append(minute)
    return {pair: compress_minutes_to_windows(times, timestep_minutes) for pair, times in candidates.items()}


def _expanded_windows(windows, duration_seconds, padding_seconds):
    merged = []
    for first, last in windows:
        start = max(0., first * 60 - padding_seconds)
        end = min(duration_seconds, last * 60 + padding_seconds)
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def refine_local_minima(sat1, sat2, jd, fr, start_second, end_second,
                        duration_seconds, step_seconds=DEFAULT_REFINEMENT_STEP_SECONDS):
    """Return (distance, seconds, location) for sampled local / horizon minima.

    Only the *global horizon* endpoints qualify as boundary events. Candidate
    window boundaries are not mistaken for a TCA. Flat separation is represented
    once, at the horizon start, rather than discarded or emitted on every sample.
    """
    _positive(step_seconds, "refinement_step_seconds")
    if not 0 <= start_second < end_second <= duration_seconds:
        raise ValueError("Refinement interval must lie inside the prediction window")

    @lru_cache(maxsize=8192)
    def distance(second):
        p1, _ = checked_state(sat1, jd, fr + second / 86400.)
        p2, _ = checked_state(sat2, jd, fr + second / 86400.)
        return distance_between(p1, p2)

    times = _grid(start_second, end_second, step_seconds)
    values = [distance(t) for t in times]
    brackets = [(times[0], times[1]), (times[-2], times[-1])]
    for i in range(1, len(times) - 1):
        if (values[i] <= values[i-1] and values[i] <= values[i+1] and
                (values[i] < values[i-1] or values[i] < values[i+1])):
            brackets.append((times[i-1], times[i+1]))

    found = []
    for lo, hi in sorted(set(brackets)):
        result = minimize_scalar(distance, bounds=(lo, hi), method="bounded",
                                 options={"xatol": TCA_TOLERANCE_SECONDS / 10})
        if not result.success or not math.isfinite(result.fun):
            raise RuntimeError("TCA refinement did not converge")
        t = float(result.x)
        if t - lo < TCA_TOLERANCE_SECONDS or hi - t < TCA_TOLERANCE_SECONDS:
            continue
        # Preserve an exact sampled minimum when it is better than the optimizer.
        indices = range(bisect_right(times, lo), bisect_left(times, hi))
        inside = [(values[i], times[i]) for i in indices]
        d, t = min([(float(result.fun), t)] + inside)
        probe = min(step_seconds / 10, (t-start_second)/2, (end_second-t)/2)
        left, right = distance(t-probe), distance(t+probe)
        if d <= left and d <= right and (d < left or d < right):
            found.append((d, t, "interior"))

    probe = min(step_seconds / 10, (end_second - start_second)/2)
    def radial_dot(second):
        p1, v1 = checked_state(sat1, jd, fr + second / 86400.)
        p2, v2 = checked_state(sat2, jd, fr + second / 86400.)
        return sum((b-a)*(vb-va) for a, b, va, vb in zip(p1, p2, v1, v2))

    if start_second == 0:
        rate = radial_dot(0)
        if rate > 0 or (rate == 0 and distance(0) <= distance(probe)):
            found.append((distance(0), 0., "window_start"))
    if end_second == duration_seconds:
        rate = radial_dot(end_second)
        if rate < 0 or (rate == 0 and distance(end_second) < distance(end_second-probe)):
            found.append((distance(end_second), end_second, "window_end"))

    unique = []
    for item in sorted(found, key=lambda item: item[1]):
        if unique and abs(item[1] - unique[-1][1]) <= TCA_TOLERANCE_SECONDS:
            if item[0] < unique[-1][0]:
                unique[-1] = item
        else:
            unique.append(item)
    return unique


def analyze_screening_window(sat1, sat2, jd, fr, window_start_minute, window_end_minute):
    """Legacy helper returning one best result; screening uses all local minima."""
    start = max(0., window_start_minute * 60 - 60)
    end = window_end_minute * 60 + 60
    minima = refine_local_minima(sat1, sat2, jd, fr, start, end, end)
    # Compatibility: a window's lowest boundary may also be its best value.
    for t in (start, end):
        p1, _ = checked_state(sat1, jd, fr + t / 86400)
        p2, _ = checked_state(sat2, jd, fr + t / 86400)
        minima.append((distance_between(p1, p2), t, "boundary"))
    distance, seconds, _ = min(minima)
    return distance, seconds


def is_persistent_co_moving_pair(sat1, sat2, jd, fr, check_minutes=10,
                                 max_distance_km=1.0, max_relative_velocity_km_s=0.01):
    """Legacy diagnostic only. A few samples cannot justify excluding a whole pair."""
    for minute in (0, check_minutes / 2, check_minutes):
        p1, v1 = checked_state(sat1, jd, fr + minute / 1440)
        p2, v2 = checked_state(sat2, jd, fr + minute / 1440)
        if distance_between(p1, p2) > max_distance_km or relative_velocity(v1, v2) > max_relative_velocity_km_s:
            return False
    return True


def find_conjunctions(satellites, jd, fr, start_time, threshold_km=50.0,
                       minutes=1440, timestep_minutes=1,
                       refinement_step_seconds=DEFAULT_REFINEMENT_STEP_SECONDS,
                       max_relative_velocity_km_s=DEFAULT_MAX_RELATIVE_SPEED_KM_S):
    _positive(minutes, "minutes")
    _positive(timestep_minutes, "timestep_minutes")
    _positive(refinement_step_seconds, "refinement_step_seconds")
    _positive(threshold_km, "threshold_km", allow_zero=True)
    _positive(max_relative_velocity_km_s, "max_relative_velocity_km_s")
    if not math.isfinite(jd) or not math.isfinite(fr):
        raise ValueError("Julian date must be finite")
    if start_time.tzinfo is None or start_time.utcoffset() is None:
        raise ValueError("start_time must include a timezone")
    satellites_by_id = {satellite.norad_id: satellite for satellite in satellites}
    if len(satellites_by_id) != len(satellites):
        raise ValueError("Duplicate NORAD IDs in screening catalog")
    if len(satellites) < 2:
        return []

    windows = find_candidate_pairs(satellites, jd, fr, threshold_km, minutes,
                                    timestep_minutes, max_relative_velocity_km_s)
    events = []
    for pair in sorted(windows):
        sat1, sat2 = (satellites_by_id[id] for id in pair)
        for first, last in _expanded_windows(windows[pair], minutes * 60, timestep_minutes * 60):
            for distance, second, location in refine_local_minima(
                    sat1, sat2, jd, fr, first, last, minutes * 60, refinement_step_seconds):
                if distance > threshold_km:
                    continue
                _, velocity1 = checked_state(sat1, jd, fr + second / 86400)
                _, velocity2 = checked_state(sat2, jd, fr + second / 86400)
                events.append(ConjunctionEvent(sat1=sat1, sat2=sat2, distance_km=distance,
                    relative_velocity_km_s=relative_velocity(velocity1, velocity2),
                    tca=start_time.astimezone(timezone.utc) + timedelta(seconds=second),
                    tca_location=location))
    return sorted(events, key=lambda event: (event.tca, event.sat1.norad_id, event.sat2.norad_id))
