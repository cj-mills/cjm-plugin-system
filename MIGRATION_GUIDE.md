# Migration Guide: Updating cjm-transcription-plugin-system

This guide shows how to migrate `cjm-transcription-plugin-system` to use the new generic `cjm-plugin-system` library.

## Overview

**Before:** All plugin infrastructure in `cjm-transcription-plugin-system`
**After:** Generic infrastructure in `cjm-plugin-system`, domain-specific code in `cjm-transcription-plugin-system`

## Step 1: Update Dependencies

### In `cjm-transcription-plugin-system/settings.ini`

```ini
[DEFAULT]
...
requirements = cjm-plugin-system jsonschema
...
```

## Step 2: Update Module Structure

### New Structure

```
cjm-transcription-plugin-system/
├── cjm_transcription_plugin_system/
│   ├── core.py              # AudioData, TranscriptionResult (domain-specific)
│   └── interface.py         # TranscriptionPlugin(PluginInterface)
└── nbs/
    ├── core.ipynb
    └── interface.ipynb
```

### Files to Remove

- `plugin_manager.py` - Use `PluginManager` from `cjm-plugin-system`
- `plugin_interface.py` - Split into generic (in cjm-plugin-system) and domain-specific

## Step 3: Update interface.ipynb

### Before (nbs/plugin_interface.ipynb)

```python
#| export
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union, List, Tuple, Generator
from pathlib import Path
from dataclasses import dataclass, field

class PluginInterface(ABC):
    """Base interface that all transcription plugins must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @property
    @abstractmethod
    def supported_formats(self) -> List[str]:
        pass

    # ... rest of methods
```

### After (nbs/interface.ipynb)

```python
#| export
from abc import ABC, abstractmethod
from typing import Union, List, Generator
from pathlib import Path

# Import generic interface from cjm-plugin-system
from cjm_plugin_system.core.interface import PluginInterface

# Import domain-specific types
from cjm_transcription_plugin_system.core import AudioData, TranscriptionResult

class TranscriptionPlugin(PluginInterface):
    """Transcription-specific plugin interface.

    This extends the generic PluginInterface with transcription-specific
    requirements.
    """

    @property
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """List of supported audio formats (e.g., ['wav', 'mp3'])."""
        pass

    @abstractmethod
    def execute(
        self,
        audio: Union[AudioData, str, Path],
        **kwargs
    ) -> TranscriptionResult:
        """Transcribe audio to text.

        Args:
            audio: Audio data or path to audio file
            **kwargs: Additional plugin-specific parameters

        Returns:
            TranscriptionResult with transcription and metadata
        """
        pass
```

## Step 4: Update Existing Plugins

All plugin implementations need minor updates:

### Before (WhisperPlugin example)

```python
from cjm_transcription_plugin_system.plugin_interface import PluginInterface

class WhisperPlugin(PluginInterface):
    ...
```

### After

```python
from cjm_transcription_plugin_system.interface import TranscriptionPlugin

class WhisperPlugin(TranscriptionPlugin):
    ...
```

## Step 5: Update Usage in Applications

### Before (in fasthtml-transcription)

```python
from cjm_transcription_plugin_system.plugin_manager import PluginManager

manager = PluginManager()
```

### After

```python
from cjm_plugin_system.core.manager import PluginManager
from cjm_transcription_plugin_system.interface import TranscriptionPlugin

manager = PluginManager(
    plugin_interface=TranscriptionPlugin,
    entry_point_group="transcription.plugins"
)
```

## Step 6: Update Plugin Packages

Each plugin package (whisper, gemini, voxtral) needs updates:

### In `setup.py` or `pyproject.toml`

**Before:**
```python
entry_points={
    'transcription.plugins': [
        'whisper=cjm_transcription_plugin_whisper.plugin:WhisperPlugin',
    ],
}
```

**After:** (No change - entry points stay the same!)
```python
entry_points={
    'transcription.plugins': [
        'whisper=cjm_transcription_plugin_whisper.plugin:WhisperPlugin',
    ],
}
```

### In plugin implementation

**Before:**
```python
from cjm_transcription_plugin_system.plugin_interface import PluginInterface
from cjm_transcription_plugin_system.core import AudioData, TranscriptionResult

class WhisperPlugin(PluginInterface):
    ...
```

**After:**
```python
from cjm_transcription_plugin_system.interface import TranscriptionPlugin
from cjm_transcription_plugin_system.core import AudioData, TranscriptionResult

class WhisperPlugin(TranscriptionPlugin):
    ...
```

## Complete Example: Updated Whisper Plugin

```python
#| export
from typing import Dict, Any, Union, List
from pathlib import Path
import logging

from cjm_transcription_plugin_system.interface import TranscriptionPlugin
from cjm_transcription_plugin_system.core import AudioData, TranscriptionResult


class WhisperPlugin(TranscriptionPlugin):
    """OpenAI Whisper transcription plugin."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{type(self).__name__}")
        self.config = {}
        self.model = None

    @property
    def name(self) -> str:
        return "whisper"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_formats(self) -> List[str]:
        return ["wav", "mp3", "flac", "m4a", "ogg", "webm"]

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "enum": ["tiny", "base", "small", "medium", "large"],
                    "default": "base",
                    "description": "Whisper model size"
                },
                "language": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": "Language code or null for auto-detection"
                }
            },
            "required": ["model"]
        }

    def get_current_config(self) -> Dict[str, Any]:
        defaults = self.get_config_defaults()
        return {**defaults, **self.config}

    def initialize(self, config: Dict[str, Any] = None) -> None:
        if config:
            is_valid, error = self.validate_config(config)
            if not is_valid:
                raise ValueError(f"Invalid configuration: {error}")

        defaults = self.get_config_defaults()
        self.config = {**defaults, **(config or {})}

        # Load Whisper model
        import whisper
        self.model = whisper.load_model(self.config["model"])

    def execute(
        self,
        audio: Union[AudioData, str, Path],
        **kwargs
    ) -> TranscriptionResult:
        # Transcribe with Whisper
        result = self.model.transcribe(
            str(audio),
            language=self.config.get("language"),
            **kwargs
        )

        return TranscriptionResult(
            text=result["text"],
            segments=result.get("segments", []),
            metadata={"language": result.get("language")}
        )

    def is_available(self) -> bool:
        try:
            import whisper
            return True
        except ImportError:
            return False

    def cleanup(self) -> None:
        self.model = None
```

## Benefits of Migration

1. **Reduced Code Duplication** - Plugin infrastructure shared across all plugin systems
2. **Easier Maintenance** - Bug fixes in one place benefit all plugin systems
3. **Consistency** - All plugin systems work the same way
4. **New Features** - New capabilities (like streaming) automatically available
5. **Better Testing** - Generic infrastructure is thoroughly tested
6. **Future Plugin Systems** - Easy to create new plugin systems (LLM, image gen, etc.)

## Testing After Migration

```python
# Test that everything still works
from cjm_plugin_system.core.manager import PluginManager
from cjm_transcription_plugin_system.interface import TranscriptionPlugin

# Create manager
manager = PluginManager(
    plugin_interface=TranscriptionPlugin,
    entry_point_group="transcription.plugins"
)

# Discover plugins
discovered = manager.discover_plugins()
print(f"Discovered {len(discovered)} plugins")

# Load a plugin
for plugin_meta in discovered:
    if plugin_meta.name == "whisper":
        success = manager.load_plugin(plugin_meta, config={"model": "base"})
        print(f"Loaded whisper: {success}")

# Execute
result = manager.execute_plugin("whisper", "test_audio.wav")
print(f"Transcription: {result.text}")
```

## Rollout Strategy

1. **Phase 1:** Install `cjm-plugin-system` in development environment
2. **Phase 2:** Update `cjm-transcription-plugin-system` to use it
3. **Phase 3:** Update plugin packages one by one (whisper, gemini, voxtral)
4. **Phase 4:** Update `fasthtml-transcription` application
5. **Phase 5:** Test thoroughly, then deploy

## Backwards Compatibility

The migration maintains backwards compatibility with existing entry points and plugin interfaces. The main changes are:

- Plugins inherit from `TranscriptionPlugin` instead of `PluginInterface`
- `PluginManager` is imported from `cjm-plugin-system`
- Manager requires explicit `plugin_interface` parameter

## Support

If issues arise during migration:
1. Check that `cjm-plugin-system` is properly installed
2. Verify imports are updated
3. Ensure `TranscriptionPlugin` is used instead of `PluginInterface`
4. Test each plugin individually before integration
