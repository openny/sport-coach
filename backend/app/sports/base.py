from abc import ABC, abstractmethod

class SportPlugin(ABC):
    sport: str

    @abstractmethod
    def segment(self, pose_series: list[dict]) -> list[dict]:
        pass

    @abstractmethod
    def extract_features(self, phases: list[dict]) -> dict:
        pass

    @abstractmethod
    def detect_issues(self, features: dict) -> list[dict]:
        pass

    @abstractmethod
    def tone_profile(self) -> dict:
        pass
