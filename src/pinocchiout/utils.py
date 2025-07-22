import itertools
import re
from collections import defaultdict
from typing import Callable, Iterable  # noqa: UP035


def find_one[T](matcher: Callable[[T], bool], iterable: Iterable[T]) -> T:
    """Find the first item in an iterable that matches a predicate."""
    for item in iterable:
        if matcher(item):
            return item

    raise KeyError(matcher, iterable)


def uniquify(name: str, existing: set[str]) -> str:
    """Make a name unique by adding a suffix if it already exists."""
    if name not in existing:
        return name

    for suffix in itertools.count(1):
        candidate = f"{name}_{suffix}"
        if candidate not in existing:
            return candidate

    raise ValueError(name, existing)


def coerce_pattern(pattern: str | re.Pattern) -> re.Pattern:
    """Coerce a pattern to a regular expression pattern."""
    if not isinstance(pattern, re.Pattern):
        return re.compile(rf"^{pattern}$", re.IGNORECASE)

    return pattern


def groupby2[T, K](iterable: Iterable[T], key: Callable[[T], K]) -> Iterable[tuple[K, list[T]]]:
    """Group items by a key function.

    Same signature as itertools.groupby, but doesn't require sequentially ordered items.
    """
    groups = defaultdict(list)
    for item in iterable:
        groups[key(item)].append(item)

    yield from groups.items()
