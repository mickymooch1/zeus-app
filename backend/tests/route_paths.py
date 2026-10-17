"""Every route path the app serves, for tests that inspect the route table.

FastAPI 0.143 stopped flattening `include_router` routers into `app.routes`:
each one now appears as an `_IncludedRouter` with no `.path`, whose
`effective_candidates()` list its routes with their full (prefixed) paths —
possibly nested further. Older FastAPI has plain routes with `.path`. This
walks both shapes, so the tests work on either version.
"""


def all_route_paths(routes):
    paths = []
    for route in routes:
        candidates = getattr(route, "effective_candidates", None)
        if callable(candidates):
            paths.extend(all_route_paths(candidates()))
        else:
            paths.append(getattr(route, "path", ""))
    return paths
