from data.data_provider import fetch_satellites
from satellite import Satellite


def get_satellites():
    satellites_data = fetch_satellites()

    return [
        Satellite(data)
        for data in satellites_data
    ]

def get_satellite_by_id(norad_id: int):
    satellites = get_satellites()

    for satellite in satellites:
        if satellite.norad_id == norad_id:
            return satellite

    return None