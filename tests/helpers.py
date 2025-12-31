import importlib

def prep_module(core_level: str, parser: str):
    module_path = f"brkraw.{core_level}"
    mod = importlib.import_module(module_path)
    return getattr(mod, parser)