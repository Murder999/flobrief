from __future__ import annotations

from collections import defaultdict

from app.main import app


def test_registered_http_method_paths_are_unique() -> None:
    routes: dict[tuple[str, str], list[str]] = defaultdict(list)
    for route in app.routes:
        for method in getattr(route, "methods", set()):
            routes[(method, route.path)].append(route.name)

    duplicates = {
        f"{method} {path}": names for (method, path), names in routes.items() if len(names) > 1
    }
    assert duplicates == {}
