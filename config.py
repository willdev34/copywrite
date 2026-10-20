"""Carrega e salva as configurações do CopyWrite."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Pasta do executável (PyInstaller) ou do código-fonte
BASE_DIR: Path = (
    Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
)
CONFIG_PATH: Path = BASE_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "speed": "normal",  # lenta, normal ou rapida
    "stop_key": "esc",
    "countdown_seconds": 5,
    "shift_enter": False,
    "long_pause_probability": 0.02,
    "window_check_every": 5,  # caracteres entre cada checagem da janela ativa
    # Intervalo base entre teclas em ms (lenta ~35, normal ~60, rapida ~100 palavras por minuto)
    "profiles": {
        "lenta": {"base_ms": 340},
        "normal": {"base_ms": 200},
        "rapida": {"base_ms": 120},
    },
}


def _merge(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    """Mescla os valores lidos sobre os padrões, sem perder chaves novas."""
    result = dict(defaults)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(defaults.get(key), dict):
            result[key] = _merge(defaults[key], value)
        else:
            result[key] = value
    return result


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    """Grava as configurações em disco."""
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Lê o config.json. Cria o arquivo com os padrões se não existir ou estiver inválido."""
    if not path.exists():
        save_config(DEFAULT_CONFIG, path)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("config.json deve ser um objeto")
    except (OSError, ValueError):
        save_config(DEFAULT_CONFIG, path)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    return _merge(DEFAULT_CONFIG, loaded)
