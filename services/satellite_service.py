from services.catalog_service import catalog


def get_satellites():
    return catalog.get_all()


def get_satellite_by_id(norad_id: int):
    return catalog.get_by_id(norad_id)