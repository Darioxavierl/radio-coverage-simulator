import sys
from pathlib import Path

# Asegura que el directorio src esté en el path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    from main import main
    sys.exit(main())