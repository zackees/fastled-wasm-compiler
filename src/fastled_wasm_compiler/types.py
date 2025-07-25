from enum import Enum


class BuildMode(Enum):
    DEBUG = "DEBUG"
    FAST_DEBUG = "FAST_DEBUG"
    QUICK = "QUICK"
    RELEASE = "RELEASE"

    @property
    def value(self):
        return self.name.lower()

    @classmethod
    def from_string(cls, mode_str: str) -> "BuildMode":
        try:
            return cls[mode_str.upper()]
        except KeyError:
            valid_modes = [mode.name for mode in cls]
            raise ValueError(f"BUILD_MODE must be one of {valid_modes}, got {mode_str}")
