"""
Email provider plugin system

This module implements a plugin-based architecture for email providers,
allowing support for multiple email services (Gmail, IMAP, Outlook, etc.)
"""
import logging
from typing import Dict, Type, Optional, List
from importlib import import_module
import pkgutil

from .base import BaseEmailProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for email provider plugins"""
    
    def __init__(self):
        self._providers: Dict[str, Type[BaseEmailProvider]] = {}
        self._instances: Dict[str, BaseEmailProvider] = {}
        self._discover_providers()
    
    def _discover_providers(self):
        """Auto-discover provider plugins in the providers package"""
        import src.providers
        
        # Get the path to the providers package
        package_path = src.providers.__path__
        
        # Discover all modules in the providers package
        for _, module_name, is_pkg in pkgutil.iter_modules(package_path):
            if is_pkg and module_name not in ['__pycache__', 'base']:
                try:
                    # Try to import the provider module
                    module = import_module(f'src.providers.{module_name}')
                    
                    # Look for a class that inherits from BaseEmailProvider
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseEmailProvider) and 
                            attr is not BaseEmailProvider):
                            
                            # Get the provider name
                            provider_name = getattr(attr, 'PROVIDER_NAME', module_name)
                            self.register(provider_name, attr)
                            logger.info(f"Auto-discovered provider: {provider_name}")
                            break
                            
                except Exception as e:
                    logger.warning(f"Failed to load provider {module_name}: {e}")
    
    def register(self, name: str, provider_class: Type[BaseEmailProvider]):
        """Register a provider class"""
        if name in self._providers:
            logger.warning(f"Provider {name} already registered, overwriting")
        self._providers[name] = provider_class
        logger.info(f"Registered provider: {name}")
    
    def get_provider_class(self, name: str) -> Optional[Type[BaseEmailProvider]]:
        """Get a provider class by name"""
        return self._providers.get(name)
    
    def get_provider(self, name: str) -> Optional[BaseEmailProvider]:
        """Get or create a provider instance"""
        if name not in self._instances:
            provider_class = self.get_provider_class(name)
            if provider_class:
                self._instances[name] = provider_class()
            else:
                return None
        return self._instances[name]
    
    def list_providers(self) -> List[str]:
        """List all registered provider names"""
        return list(self._providers.keys())
    
    def clear_instances(self):
        """Clear all cached provider instances"""
        self._instances.clear()


# Global provider registry
provider_registry = ProviderRegistry()


def get_provider(name: str) -> Optional[BaseEmailProvider]:
    """Get a provider instance by name"""
    return provider_registry.get_provider(name)


def list_providers() -> List[str]:
    """List all available providers"""
    return provider_registry.list_providers()


def register_provider(name: str, provider_class: Type[BaseEmailProvider]):
    """Manually register a provider"""
    provider_registry.register(name, provider_class)