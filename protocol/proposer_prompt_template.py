# Extracted verbatim from the frozen proposer runner.

def prompt(task: dict[str, Any], image_size: tuple[int, int]) -> str:
    width, height = image_size
    return f"""You are the geometry proposer for a visual-measurement system. Use only the supplied image and question; no answer key or human annotation is available.

Question: {task['question']}
Instrument family: {task['instrument_family']}
Original image size: {width} by {height} pixels.

Return coordinates normalized to [0,1000] over the full original image: left=0, right=1000, top=0, bottom=1000. Use [-1,-1] and include=false rather than inventing unavailable geometry.

State representation:
- position_or_boundary: the two target points bracket the one physical position or boundary that encodes the answer.
- span_difference: only when the question asks for a length, width, distance, or span; the two target points are the two physical endpoints whose scale-coordinate difference is the answer.

Locate one relevant scale branch. axis_low_xy and axis_high_xy follow increasing numeric values. anchor_low/high are two visibly grounded numeric tick labels on that same branch, with the exact values printed at those ticks. local_tick_centers_xy are 2-12 consecutive adjacent smallest visible graduations near the target, ordered from lower to higher value. Do not substitute clearer major ticks when smaller adjacent graduations are visible. minor_tick_value is the numeric difference between adjacent smallest ticks. direct_reading_low/high are your direct visible reading interval.

For rulers whose object does not start at zero, preserve both endpoints and compute a difference. For thermometers and liquid columns, use the end/boundary of the continuous state. Recheck that target, anchors, and ticks all belong to the same requested instrument and branch.

Return one compact JSON object with exactly these keys and no Markdown:
{{"include":true,"confidence":0.8,"state_operator":"position_or_boundary","scale_branch":"...","unit":"...","axis_low_xy":[0,0],"axis_high_xy":[0,0],"target_state_points_xy":[[0,0],[0,0]],"anchor_low_xy":[0,0],"anchor_low_value":0,"anchor_high_xy":[0,0],"anchor_high_value":0,"local_tick_centers_xy":[[0,0],[0,0]],"minor_tick_value":0,"direct_reading_low":0,"direct_reading_high":0,"brief_evidence":"..."}}

axis_low_xy and axis_high_xy must each be one [x,y] point. target_state_points_xy must always contain exactly two [x,y] points; duplicate a point when the target is a single position. Do not introduce keys named position_or_boundary, span_difference, anchor_low, or anchor_high."""
