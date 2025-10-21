#!/usr/bin/env python
"""
Test script for the generic plugin system.

This demonstrates how to:
1. Create a domain-specific plugin interface
2. Implement concrete plugins
3. Use PluginManager to manage plugins
"""

import logging
from typing import Dict, Any, List
from pathlib import Path

from cjm_plugin_system.core.interface import PluginInterface
from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.metadata import PluginMeta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


# Example 1: Text Processing Plugin System
# ==========================================

class TextProcessingPlugin(PluginInterface):
    """Domain-specific plugin interface for text processing."""

    @property
    def supported_formats(self) -> List[str]:
        """File formats this plugin can process."""
        raise NotImplementedError

    def execute(self, text: str, **kwargs) -> str:
        """Process text and return transformed result."""
        raise NotImplementedError


class UpperCasePlugin(TextProcessingPlugin):
    """Plugin that converts text to uppercase."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{type(self).__name__}")
        self.config = {}

    @property
    def name(self) -> str:
        return "uppercase"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_formats(self) -> List[str]:
        return ["txt", "md"]

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "preserve_newlines": {
                    "type": "boolean",
                    "default": True,
                    "description": "Preserve newline characters"
                }
            }
        }

    def get_current_config(self) -> Dict[str, Any]:
        defaults = self.get_config_defaults()
        return {**defaults, **self.config}

    def initialize(self, config: Dict[str, Any] = None) -> None:
        defaults = self.get_config_defaults()
        self.config = {**defaults, **(config or {})}
        self.logger.info(f"Initialized {self.name} with config: {self.config}")

    def execute(self, text: str, **kwargs) -> str:
        self.logger.info(f"Processing text with {self.name}")
        return text.upper()

    def is_available(self) -> bool:
        return True


class ReversePlugin(TextProcessingPlugin):
    """Plugin that reverses text."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{type(self).__name__}")
        self.config = {}

    @property
    def name(self) -> str:
        return "reverse"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_formats(self) -> List[str]:
        return ["txt"]

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reverse_words": {
                    "type": "boolean",
                    "default": False,
                    "description": "Reverse individual words instead of entire text"
                }
            }
        }

    def get_current_config(self) -> Dict[str, Any]:
        defaults = self.get_config_defaults()
        return {**defaults, **self.config}

    def initialize(self, config: Dict[str, Any] = None) -> None:
        defaults = self.get_config_defaults()
        self.config = {**defaults, **(config or {})}
        self.logger.info(f"Initialized {self.name} with config: {self.config}")

    def execute(self, text: str, **kwargs) -> str:
        self.logger.info(f"Processing text with {self.name}")
        if self.config.get("reverse_words", False):
            return " ".join(word[::-1] for word in text.split())
        return text[::-1]

    def is_available(self) -> bool:
        return True


def test_plugin_system():
    """Test the generic plugin system."""

    print("=" * 80)
    print("TESTING GENERIC PLUGIN SYSTEM")
    print("=" * 80)

    # Create a plugin manager using the generic PluginInterface
    # (In production, you'd use a domain-specific interface like TranscriptionPlugin)
    print("\n1. Creating PluginManager with generic PluginInterface...")
    manager = PluginManager(
        plugin_interface=PluginInterface,
        entry_point_group="text_processing.plugins"
    )
    print(f"   ✓ Manager created with interface: {manager.plugin_interface.__name__}")

    # Since we don't have installed plugins, we'll create temporary plugin files
    print("\n2. Creating test plugins...")

    import tempfile
    import os

    # Create uppercase plugin file
    uppercase_code = '''
from typing import Dict, Any, List
from cjm_plugin_system.core.interface import PluginInterface

class UpperCasePlugin(PluginInterface):
    """Plugin that converts text to uppercase."""

    def __init__(self):
        self.config = {}

    @property
    def name(self) -> str:
        return "uppercase"

    @property
    def version(self) -> str:
        return "1.0.0"

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "preserve_newlines": {
                    "type": "boolean",
                    "default": True,
                    "description": "Preserve newline characters"
                }
            }
        }

    def get_current_config(self) -> Dict[str, Any]:
        defaults = self.get_config_defaults()
        return {**defaults, **self.config}

    def initialize(self, config: Dict[str, Any] = None) -> None:
        defaults = self.get_config_defaults()
        self.config = {**defaults, **(config or {})}

    def execute(self, text: str, **kwargs) -> str:
        return text.upper()

    def is_available(self) -> bool:
        return True
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='_uppercase.py', delete=False) as f:
        f.write(uppercase_code)
        uppercase_path = f.name

    # Create reverse plugin file
    reverse_code = '''
from typing import Dict, Any, List
from cjm_plugin_system.core.interface import PluginInterface

class ReversePlugin(PluginInterface):
    """Plugin that reverses text."""

    def __init__(self):
        self.config = {}

    @property
    def name(self) -> str:
        return "reverse"

    @property
    def version(self) -> str:
        return "1.0.0"

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reverse_words": {
                    "type": "boolean",
                    "default": False,
                    "description": "Reverse individual words instead of entire text"
                }
            }
        }

    def get_current_config(self) -> Dict[str, Any]:
        defaults = self.get_config_defaults()
        return {**defaults, **self.config}

    def initialize(self, config: Dict[str, Any] = None) -> None:
        defaults = self.get_config_defaults()
        self.config = {**defaults, **(config or {})}

    def execute(self, text: str, **kwargs) -> str:
        if self.config.get("reverse_words", False):
            return " ".join(word[::-1] for word in text.split())
        return text[::-1]

    def is_available(self) -> bool:
        return True
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='_reverse.py', delete=False) as f:
        f.write(reverse_code)
        reverse_path = f.name

    print("   ✓ Test plugin files created")

    # Load plugins from files
    print("\n3. Loading plugins from module files...")
    success1 = manager.load_plugin_from_module(uppercase_path)
    success2 = manager.load_plugin_from_module(reverse_path)
    print(f"   ✓ Uppercase plugin loaded: {success1}")
    print(f"   ✓ Reverse plugin loaded: {success2}")

    # List loaded plugins
    print("\n4. Listing loaded plugins...")
    plugins = manager.list_plugins()
    for p in plugins:
        print(f"   - {p.name} v{p.version} (enabled: {p.enabled})")

    # Test plugin execution
    print("\n5. Testing plugin execution...")
    test_text = "Hello World"

    result1 = manager.execute_plugin("uppercase", test_text)
    print(f"   Input: '{test_text}'")
    print(f"   Uppercase: '{result1}'")

    result2 = manager.execute_plugin("reverse", test_text)
    print(f"   Reverse: '{result2}'")

    # Test configuration management
    print("\n6. Testing configuration management...")

    # Get current config
    config = manager.get_plugin_config("reverse")
    print(f"   Current reverse plugin config: {config}")

    # Update config
    success = manager.update_plugin_config("reverse", {"reverse_words": True})
    print(f"   ✓ Config updated: {success}")

    # Execute with new config
    result3 = manager.execute_plugin("reverse", test_text)
    print(f"   Reverse (word mode): '{result3}'")

    # Test validation
    print("\n7. Testing configuration validation...")
    is_valid, error = manager.validate_plugin_config("uppercase", {"preserve_newlines": True})
    print(f"   Valid config: {is_valid}")

    is_valid, error = manager.validate_plugin_config("uppercase", {"invalid_key": "value"})
    print(f"   Invalid config: {is_valid}")

    # Test enable/disable
    print("\n8. Testing enable/disable...")
    manager.disable_plugin("uppercase")
    print(f"   ✓ Uppercase plugin disabled")

    try:
        manager.execute_plugin("uppercase", test_text)
        print("   ✗ Should have raised error!")
    except ValueError as e:
        print(f"   ✓ Expected error caught: {str(e)}")

    manager.enable_plugin("uppercase")
    print(f"   ✓ Uppercase plugin re-enabled")

    # Test streaming support
    print("\n9. Testing streaming support...")
    supports = manager.check_streaming_support("uppercase")
    print(f"   Uppercase supports streaming: {supports}")

    streaming_plugins = manager.get_streaming_plugins()
    print(f"   Streaming plugins: {streaming_plugins}")

    # Get all schemas
    print("\n10. Getting all plugin schemas...")
    all_schemas = manager.get_all_plugin_schemas()
    print(f"   Retrieved schemas for {len(all_schemas)} plugins")
    for name, schema in all_schemas.items():
        props = schema.get("properties", {})
        print(f"   - {name}: {len(props)} configuration properties")

    # Cleanup
    print("\n11. Cleaning up...")
    manager.unload_plugin("uppercase")
    manager.unload_plugin("reverse")
    print(f"   ✓ Plugins unloaded")

    # Remove temp files
    os.unlink(uppercase_path)
    os.unlink(reverse_path)
    print(f"   ✓ Temporary files removed")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED! ✓")
    print("=" * 80)
    print("\nThe generic plugin system is working correctly!")
    print("You can now use it to create domain-specific plugin systems like:")
    print("  - TranscriptionPlugin (audio transcription)")
    print("  - LLMPlugin (language models)")
    print("  - ImageGenPlugin (image generation)")
    print("  - VideoPlugin (video processing)")
    print("  - And more!")


if __name__ == "__main__":
    test_plugin_system()
