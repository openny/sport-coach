from ..base import SportPlugin
from ...analysis.features import extract_basic_metrics
from .heuristics import window_hits, value_hits

class SkiPlugin(SportPlugin):
    sport = "ski"

    def segment(self, pose_series: list[dict]) -> list[dict]:
        if not pose_series:
            return []
        return [{"phase": "full", "t0": pose_series[0]["t"], "t1": pose_series[-1]["t"], "pose": pose_series}]

    def extract_features(self, phases: list[dict]) -> dict:
        if not phases:
            return {}
        metrics = extract_basic_metrics(phases[0]["pose"])
        return {"phase": phases[0]["phase"], "metrics": metrics}

    def detect_issues(self, features: dict) -> list[dict]:
        m = features.get("metrics", {})
        issues = []

        for (t0, t1) in window_hits(m.get("sep_proxy", []), "sep", threshold=20, min_count=4):
            issues.append({
                "code": "upper_body_rotation",
                "severity": 3,
                "title": "상체 회전이 과해요",
                "evidence": {"sep_proxy_abs_deg": ">=20"},
                "range": {"t0": t0, "t1": t1},
            })

        near0 = []
        for p in m.get("sep_proxy", []):
            near0.append({"t": p["t"], "near": 1 if abs(p["sep"]) < 8 else 0})
        run = []
        for p in near0:
            if p["near"] == 1:
                run.append(p["t"])
            else:
                if len(run) >= 5:
                    issues.append({
                        "code": "lack_of_separation",
                        "severity": 2,
                        "title": "외향(힙-상체 분리)이 부족해요",
                        "evidence": {"sep_proxy_abs_deg": "<8 for a while"},
                        "range": {"t0": run[0], "t1": run[-1]},
                    })
                run = []
        if len(run) >= 5:
            issues.append({
                "code": "lack_of_separation",
                "severity": 2,
                "title": "외향(힙-상체 분리)이 부족해요",
                "evidence": {"sep_proxy_abs_deg": "<8 for a while"},
                "range": {"t0": run[0], "t1": run[-1]},
            })

        lk = [{"t": x["t"], "v": x["lk"]} for x in m.get("knee_angles", []) if x["lk"] is not None]
        for (t0, t1) in value_hits([{"t": p["t"], "k": 180-p["v"]} for p in lk], "k", threshold=50, min_count=5):
            issues.append({
                "code": "knee_collapse_proxy",
                "severity": 2,
                "title": "무릎이 과하게 접히며 버티는 구간이 있어요",
                "evidence": {"knee_flex_deg": ">=50 (proxy)"},
                "range": {"t0": t0, "t1": t1},
            })

        lean = m.get("torso_lean", [])
        for (t0, t1) in window_hits(lean, "lean", threshold=18, min_count=4):
            issues.append({
                "code": "excessive_vertical_movement_proxy",
                "severity": 1,
                "title": "상체 움직임(업다운/흔들림)이 커 보여요",
                "evidence": {"torso_lean_abs_deg": ">=18"},
                "range": {"t0": t0, "t1": t1},
            })

        issues.append({
            "code": "late_transition_placeholder",
            "severity": 1,
            "title": "턴 전환 타이밍은 다음 버전에서 더 정확히 잡아드릴게요",
            "evidence": {"note": "MVP placeholder"},
            "range": {"t0": 0, "t1": 0},
        })

        issues = sorted(issues, key=lambda x: x["severity"], reverse=True)[:5]
        return issues

    def tone_profile(self) -> dict:
        return {
            "style": "friendly_coach",
            "glossary": ["외향", "전환", "폴라인", "엣지", "하중", "분리(힙-상체)"],
        }
