"""
Atualiza as URLs do Twilio para apontar para o backend em produção.

Preferir o setup completo:
    python scripts/setup_twilio_completo.py

Este script mantém compatibilidade com chamadas antigas.
"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).parent / "setup_twilio_completo.py"
    sys.exit(subprocess.call([sys.executable, str(script), *sys.argv[1:]]))
