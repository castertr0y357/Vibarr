from abc import ABC, abstractmethod
from typing import List, Dict, Any

class MediaProvider(ABC):
    @abstractmethod
    def get_library_titles(self) -> List[str]:
        """Returns a list of all titles currently in the library."""
        pass

    @abstractmethod
    def get_recent_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Returns recent watch history events."""
        pass

    @abstractmethod
    def sync_collection(self, titles: List[str], collection_name: str):
        """Creates or updates a collection with the given titles."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Verifies connection to the media server."""
        pass

    @abstractmethod
    def get_available_libraries(self) -> List[str]:
        """Returns a list of all library names available on the server."""
        pass
