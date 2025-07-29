"""
Base API client with common functionality
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """Base class for API clients"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.setup_client()
    
    @abstractmethod
    def setup_client(self):
        """Initialize the API client"""
        pass
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the API"""
        pass
    
    def handle_api_error(self, error: Exception, context: str = "API call"):
        """Handle API errors with consistent logging"""
        logger.error(f"{context} failed: {str(error)}")
        raise