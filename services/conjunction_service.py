from services.screening_service import screening_service

def get_conjunctions():
    return screening_service.get_events()