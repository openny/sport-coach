def window_hits(series, key, threshold, min_count=4):
    hits = []
    run = []
    for p in series:
        v = p.get(key)
        if v is None:
            continue
        if abs(v) >= threshold:
            run.append(p["t"])
        else:
            if len(run) >= min_count:
                hits.append((run[0], run[-1]))
            run = []
    if len(run) >= min_count:
        hits.append((run[0], run[-1]))
    return hits

def value_hits(series, key, threshold, min_count=4):
    hits = []
    run = []
    for p in series:
        v = p.get(key)
        if v is None:
            continue
        if v >= threshold:
            run.append(p["t"])
        else:
            if len(run) >= min_count:
                hits.append((run[0], run[-1]))
            run = []
    if len(run) >= min_count:
        hits.append((run[0], run[-1]))
    return hits
