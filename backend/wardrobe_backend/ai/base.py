from abc import ABC, abstractmethod
from pathlib import Path
from ..schema import ClothingAnalysis
class ClothingAnalyzer(ABC):
    @abstractmethod
    def analyze(self, image_path: Path, image_id: str) -> ClothingAnalysis: ...
