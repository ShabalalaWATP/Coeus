"""Small confusion-matrix helper for routing evaluation reports."""


def route_counts(route: str, outcomes: tuple[tuple[str, str], ...]) -> tuple[int, int, int]:
    true_positive = sum(expected == route and actual == route for expected, actual in outcomes)
    false_positive = sum(expected != route and actual == route for expected, actual in outcomes)
    false_negative = sum(expected == route and actual != route for expected, actual in outcomes)
    return true_positive, false_positive, false_negative
