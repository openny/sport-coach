import math

def angle(a, b, c):
    bax, bay = a["x"]-b["x"], a["y"]-b["y"]
    bcx, bcy = c["x"]-b["x"], c["y"]-b["y"]
    dot = bax*bcx + bay*bcy
    na = math.hypot(bax, bay)
    nc = math.hypot(bcx, bcy)
    if na*nc == 0:
        return None
    cosv = max(min(dot/(na*nc), 1.0), -1.0)
    return math.degrees(math.acos(cosv))

def extract_basic_metrics(pose_series: list[dict]) -> dict:
    knee_angles = []
    torso_lean = []
    sep_proxy = []
    times = []

    for f in pose_series:
        k = f["kpts"]
        t = f["t"]
        times.append(t)

        lk = angle(k[23], k[25], k[27])
        rk = angle(k[24], k[26], k[28])
        knee_angles.append({"t": t, "lk": lk, "rk": rk})

        hip = {"x": (k[23]["x"]+k[24]["x"])/2, "y": (k[23]["y"]+k[24]["y"])/2}
        sh = {"x": (k[11]["x"]+k[12]["x"])/2, "y": (k[11]["y"]+k[12]["y"])/2}
        dx, dy = sh["x"]-hip["x"], sh["y"]-hip["y"]
        lean = math.degrees(math.atan2(dx, -dy))
        torso_lean.append({"t": t, "lean": lean})

        sh_ang = math.degrees(math.atan2(k[12]["y"]-k[11]["y"], k[12]["x"]-k[11]["x"]))
        hip_ang = math.degrees(math.atan2(k[24]["y"]-k[23]["y"], k[24]["x"]-k[23]["x"]))
        sep_proxy.append({"t": t, "sep": sh_ang - hip_ang})

    return {
        "knee_angles": knee_angles,
        "torso_lean": torso_lean,
        "sep_proxy": sep_proxy,
        "times": times,
    }
