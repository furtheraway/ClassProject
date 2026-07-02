import math

from django.conf import settings


def current_bonus_score(project_count):
    """Bonus score shown on the stats card (SPEC §3.4).

    Logistic S-curve: stays near the maximum while the class still needs
    projects, drops fastest around the midpoint, floors at the minimum.
    Constants live in settings.BONUS_SCORE so the curve can be tuned
    without code changes.
    """
    cfg = settings.BONUS_SCORE
    span = cfg["max"] - cfg["min"]
    exponent = (project_count - cfg["midpoint"]) / cfg["steepness"]
    return round(cfg["min"] + span / (1 + math.exp(exponent)))
