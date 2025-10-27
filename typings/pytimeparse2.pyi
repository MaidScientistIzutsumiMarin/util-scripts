from datetime import timedelta

def parse(
    sval: str | float,
    granularity: str = "seconds",
    raise_exception: bool = False,
    as_timedelta: bool = False,
) -> int | float | timedelta | None: ...
