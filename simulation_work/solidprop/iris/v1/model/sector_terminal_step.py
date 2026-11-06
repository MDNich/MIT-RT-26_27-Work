"""Preserve a well-resolved final interval without exceeding the time-step ceiling."""


def end_step(wall,state,requested,ceiling):
    if len(state.nodes)==2:
        radius, end_dt, _, _ = wall.motion(state,2*ceiling)
        # Avoid spending almost an entire ordinary step then leaving a thin
        # sliver to solve. Reserve most of one normal step for exhaustion.
        if radius==wall.interface and requested<end_dt<requested+.90*ceiling and end_dt>.90*ceiling:
            return end_dt-.90*ceiling
    return requested
