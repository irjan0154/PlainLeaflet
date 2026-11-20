"""Load the pure-logic block of the contract without importing GenLayer."""
import pathlib
import types

_CONTRACT = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "plain_leaflet.py"
_BEGIN = "# ==== PURE LOGIC BEGIN ===="
_END = "# ==== PURE LOGIC END ===="


def load_pure() -> types.SimpleNamespace:
    source = _CONTRACT.read_text(encoding="utf-8")
    start = source.index(_BEGIN)
    stop = source.index(_END)
    block = "import hashlib\nimport json\nimport re\n" + source[start:stop]
    namespace: dict = {}
    exec(compile(block, str(_CONTRACT), "exec"), namespace)
    return types.SimpleNamespace(**{k: v for k, v in namespace.items() if not k.startswith("__")})


L = load_pure()
