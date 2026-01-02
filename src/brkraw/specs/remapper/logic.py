from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
import inspect
from types import ModuleType
from typing import Any, Callable, Optional, List, Dict, Tuple, Set, Union
import yaml
from .validator import validate_spec


def _load_transforms_from_source(src: str) -> Dict[str, Callable[[Any], Any]]:
    """Execute a Python snippet and extract public callables.

    Args:
        src: Python source code that defines transform callables.

    Returns:
        A mapping of transform names to callables defined in the snippet.
    """
    mod = ModuleType("spec_transforms")
    exec(src, mod.__dict__)
    return {
        name: obj
        for name, obj in mod.__dict__.items()
        if callable(obj) and not name.startswith("_") and not inspect.isclass(obj)
    }

def _normalize_transforms_source(
    transforms_source: Any,
    *,
    base_dir: Path,
) -> List[Path]:
    if transforms_source is None:
        return []
    sources: List[str]
    if isinstance(transforms_source, str):
        sources = [transforms_source]
    elif isinstance(transforms_source, list) and all(isinstance(item, str) for item in transforms_source):
        sources = transforms_source
    else:
        raise ValueError("transforms_source must be a string or list of strings.")
    paths: List[Path] = []
    for item in sources:
        src = Path(item)
        if not src.is_absolute():
            src = (base_dir / src).resolve()
        paths.append(src)
    return paths


def _collect_transforms_paths(spec: Dict[str, Any], spec_path: Path) -> List[Path]:
    paths: List[Path] = []
    meta = spec.get("__meta__")
    if isinstance(meta, dict) and meta.get("transforms_source"):
        paths.extend(_normalize_transforms_source(meta.get("transforms_source"), base_dir=spec_path.parent))
    for value in spec.values():
        if not isinstance(value, dict):
            continue
        child_meta = value.get("__meta__")
        if isinstance(child_meta, dict) and child_meta.get("transforms_source"):
            paths.extend(
                _normalize_transforms_source(child_meta.get("transforms_source"), base_dir=spec_path.parent)
            )
    return paths


def _load_spec_data(spec_path: Path, stack: Set[Path]) -> Tuple[Dict[str, Any], List[Path]]:
    spec_path = spec_path.resolve()
    if spec_path in stack:
        raise ValueError(f"Circular spec include detected: {spec_path}")
    if spec_path.suffix not in (".yaml", ".yml"):
        raise ValueError("Spec file must be a .yaml/.yml file.")
    stack.add(spec_path)
    try:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValueError("Spec file must contain a mapping.")
        transforms_paths = _collect_transforms_paths(spec, spec_path)
        include_list: List[str] = []
        meta = spec.get("__meta__")
        include_mode = "override"
        if isinstance(meta, dict) and meta.get("include_mode"):
            include_mode = str(meta["include_mode"])
            if include_mode not in {"override", "strict"}:
                raise ValueError("include_mode must be 'override' or 'strict'.")
        if isinstance(meta, dict) and "include" in meta:
            include = meta.get("include")
            if isinstance(include, str):
                include_list = [include]
            elif isinstance(include, list) and all(isinstance(item, str) for item in include):
                include_list = include
            else:
                raise ValueError("__meta__.include must be a string or list of strings.")

        merged: Dict[str, Any] = {}
        for item in include_list:
            inc_path = Path(item)
            if not inc_path.is_absolute():
                inc_path = (spec_path.parent / inc_path).resolve()
            inc_spec, inc_transforms = _load_spec_data(inc_path, stack)
            transforms_paths.extend(inc_transforms)
            for key, value in inc_spec.items():
                if key == "__meta__":
                    continue
                if include_mode == "strict" and key in merged:
                    raise ValueError(f"Spec include conflict for key {key!r} in {spec_path}")
                merged[key] = value

        for key, value in spec.items():
            if key == "__meta__":
                continue
            if include_mode == "strict" and key in merged:
                raise ValueError(f"Spec include conflict for key {key!r} in {spec_path}")
            merged[key] = value

        if isinstance(meta, dict):
            meta_clean = dict(meta)
            meta_clean.pop("include", None)
            meta_clean.pop("include_mode", None)
            merged["__meta__"] = meta_clean

        return merged, transforms_paths
    finally:
        stack.remove(spec_path)


def load_spec(
    spec_source: Union[str, Path],
    *,
    validate: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Callable]]:
    """Load spec YAML plus optional transforms from files.

    Args:
        spec_source: YAML file path.
        validate: If True, validate the spec before returning.

    Returns:
        Tuple of (spec, transforms) where transforms is a name->callable mapping.

    Notes:
        Transforms are loaded from ``__meta__.transforms_source`` when present,
        including sources referenced via ``__meta__.include``.
    """
    spec_path = Path(spec_source)
    spec, transforms_paths = _load_spec_data(spec_path, set())
    transforms_path: List[Path] = []
    if transforms_paths:
        seen: Set[Path] = set()
        for item in transforms_paths:
            if item not in seen:
                transforms_path.append(item)
                seen.add(item)
    if validate:
        validate_spec(spec, transforms_source=transforms_path)

    transforms: Dict[str, Callable] = {}
    if not transforms_path:
        return spec, transforms

    for path in transforms_path:
        transforms_text = path.read_text(encoding="utf-8")
        transforms.update(_load_transforms_from_source(transforms_text))
    return spec, transforms


def _get_params_from_map(params_map: Mapping[str, Any], file: str, reco_id: Optional[int]):
    if file == "subject":
        return params_map.get("subject")
    params = params_map.get(file)
    if params is None:
        return None
    if file in ("visu_pars", "reco") and isinstance(params, Mapping):
        if reco_id is None:
            if len(params) == 1:
                return next(iter(params.values()))
            return None
        return params.get(reco_id)
    return params


def _get_params(source, file: str, reco_id: Optional[int]):
    """Return the parameter container for a requested file type.

    Args:
        source: Scan-like object, Study-like object, or mapping of parameters.
        file: Parameter file identifier (method, acqp, visu_pars, reco, subject).
        reco_id: Optional reconstruction id for reco/visu_pars.

    Returns:
        Parameter container or None if the file type is unsupported.
    """
    if isinstance(source, Mapping):
        return _get_params_from_map(source, file, reco_id)
    if file == "subject":
        return getattr(source, "subject", None)
    if file == "method":
        return source.method
    if file == "acqp":
        return source.acqp
    if file == "visu_pars":
        return source.get_reco(reco_id or 1).visu_pars
    if file == "reco":
        return source.get_reco(reco_id or 1).reco
    return None


def _resolve_value(source, sources, transforms: Dict[str, Callable], result_ctx: Dict[str, Any]):
    """Resolve the first available value from a list of source descriptors.

    Args:
        source: Scan-like object or mapping of parameter containers.
        sources: Iterable of dicts with file/key(/reco_id) selectors or inline inputs.
        transforms: Transform registry for post-processing.
        result_ctx: Current output context for "ref" lookups.

    Returns:
        The first matching value, or None if nothing is found.
    """
    for src in sources:
        if "inputs" in src:
            inputs = _resolve_inputs(source, src["inputs"], transforms, result_ctx)
            if "transform" in src:
                return _apply_inputs_transform(inputs, transforms, src["transform"])
            return inputs
        params = _get_params(source, src["file"], src.get("reco_id"))
        if params is None:
            continue
        key = src["key"]
        if hasattr(params, key):
            return getattr(params, key)
        if isinstance(params, Mapping):
            if key in params:
                return params[key]
        elif hasattr(params, "keys"):
            if key in params.keys():
                return params[key]
    return None


def _set_nested(d: Dict[str, Any], dotted: str, value: Any) -> None:
    """Assign a value into a nested dict using dotted keys.

    Args:
        d: Target dictionary to mutate.
        dotted: Dotted key path like "a.b.c".
        value: Value to set at the leaf key.
    """
    cur = d
    parts = dotted.split(".")
    for key in parts[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    cur[parts[-1]] = value


def _get_nested(d: Dict[str, Any], dotted: str) -> Any:
    """Fetch a nested value from a dict using dotted keys.

    Args:
        d: Dictionary to traverse.
        dotted: Dotted key path like "a.b.c".

    Returns:
        The nested value or None if the path does not exist.
    """
    cur: Any = d
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _apply_transform_chain(value: Any, transforms: Dict[str, Callable], names: Any) -> Any:
    """Apply one or more transform functions to a value.

    Args:
        value: Input value.
        transforms: Mapping of transform names to callables.
        names: Transform name or list of names; falsy means no-op.

    Returns:
        The transformed value.

    Notes:
        Transforms are applied even when ``value`` is ``None``. If a transform
        cannot handle ``None``, it should guard accordingly.
    """
    if not names:
        return value
    chain = names if isinstance(names, list) else [names]
    val = value
    for tname in chain:
        val = transforms[tname](val)
    return val


def _enforce_study_rules(spec: Mapping[str, Any]) -> None:
    has_subject_source = False
    disallowed_files: Set[str] = set()

    def check_sources(sources: List[Dict[str, Any]]) -> None:
        nonlocal has_subject_source
        for src in sources:
            file = src.get("file")
            if file == "subject":
                has_subject_source = True
            elif file is not None:
                disallowed_files.add(str(file))

    for _, rule in spec.items():
        if "sources" in rule:
            check_sources(rule.get("sources", []))
        if "inputs" in rule:
            for input_spec in rule.get("inputs", {}).values():
                if "sources" in input_spec:
                    check_sources(input_spec.get("sources", []))

    if disallowed_files:
        raise ValueError(
            "Study remap only supports subject sources; "
            f"found: {sorted(disallowed_files)}."
        )
    if not has_subject_source:
        raise ValueError("Study remap requires at least one subject source.")


def _is_study_like(source: Any) -> bool:
    return hasattr(source, "scans") and hasattr(source, "has_subject")


def _resolve_input(
    source,
    spec: Dict[str, Any],
    transforms: Dict[str, Callable],
    result_ctx: Dict[str, Any],
) -> Any:
    """Resolve a single input value based on a spec entry.

    Args:
        source: Scan-like object or mapping of parameter containers.
        spec: Input spec containing sources/const/ref/default/transform.
        transforms: Transform registry for post-processing.
        result_ctx: Current output context for "ref" lookups.

    Returns:
        The resolved input value, possibly transformed.
    """
    if "const" in spec:
        return spec["const"]
    if "ref" in spec:
        return _get_nested(result_ctx, spec["ref"])

    raw = _resolve_value(source, spec.get("sources", []), transforms, result_ctx)
    if raw is None:
        if "default" in spec:
            raw = spec["default"]
        elif spec.get("required", False):
            raise KeyError(f"Required input missing: {spec}")
        else:
            return None

    return _apply_transform_chain(raw, transforms, spec.get("transform"))


def _resolve_inputs(
    source,
    inputs_spec: Dict[str, Any],
    transforms: Dict[str, Callable],
    result_ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve a dict of input values for a rule.

    Args:
        source: Scan-like object or mapping of parameter containers.
        inputs_spec: Mapping of input names to input specs.
        transforms: Transform registry for post-processing.
        result_ctx: Current output context for "ref" lookups.

    Returns:
        Mapping of input names to resolved values.
    """
    inputs: Dict[str, Any] = {}
    for name, spec in inputs_spec.items():
        inputs[name] = _resolve_input(source, spec, transforms, result_ctx)
    return inputs


def _apply_inputs_transform(
    inputs: Dict[str, Any],
    transforms: Dict[str, Callable],
    name: Union[str, List[str]],
) -> Any:
    if isinstance(name, list):
        if not name:
            raise ValueError("Transform chain cannot be empty.")
        head, *tail = name
        value = _apply_inputs_transform(inputs, transforms, head)
        return _apply_transform_chain(value, transforms, tail)

    transform = transforms[name]
    signature = inspect.signature(transform)
    params = signature.parameters
    var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if not var_kw:
        expected = {
            p.name
            for p in params.values()
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
        required = {
            p.name
            for p in params.values()
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            and p.default is inspect._empty
        }
        extra = set(inputs.keys()) - expected
        missing = required - set(inputs.keys())
        if extra or missing:
            raise ValueError(
                f"Transform {name!r} kwargs mismatch. "
                f"extra={sorted(extra)} missing={sorted(missing)}"
            )
    return transform(**inputs)


def map_parameters(
    source,
    spec: Mapping[str, Any],
    transforms: Optional[Dict[str, Callable]] = None,
    *,
    validate: bool = False,
) -> Dict[str, Any]:
    """Map parameters to a nested dict according to spec rules.

    Args:
        source: Scan/Study-like object or mapping of parameter containers.
        spec: Mapping of output keys to resolution rules.
        transforms: Transform registry used by rules (optional).
        validate: If True, validate the spec before mapping.

    Returns:
        Nested dictionary of mapped outputs.

    Notes:
        Transforms are invoked even when the resolved value is ``None``. Make
        sure transform functions handle ``None`` when missing data is expected.
    """
    if validate:
        validate_spec(spec)
    if _is_study_like(source):
        _enforce_study_rules(spec)
    if transforms is None:
        transforms = {}
    result: Dict[str, Any] = {}
    for out_key, rule in spec.items():
        if out_key == "__meta__":
            continue
        try:
            if "inputs" in rule:
                inputs = _resolve_inputs(source, rule["inputs"], transforms, result)
                if "transform" in rule:
                    val = _apply_inputs_transform(inputs, transforms, rule["transform"])
                else:
                    val = inputs
            else:
                raw = _resolve_value(source, rule.get("sources", []), transforms, result)
                val = _apply_transform_chain(raw, transforms, rule.get("transform"))

            if "." in out_key:
                _set_nested(result, out_key, val)
            else:
                result[out_key] = val
        except Exception as exc:
            msg = f"Error mapping {out_key!r} with rule {rule!r}: {exc}"
            raise type(exc)(msg) from exc
    return result


__all__ = [
    "load_spec",
    "map_parameters",
]


if __name__ == "__main__":
    import tempfile

    class _Params(dict):
        """Minimal dict-like params with attribute access."""

        def __getattr__(self, name: str):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

    class _Reco:
        def __init__(self, reco_id: int, visu_pars: Dict[str, Any], reco: Dict[str, Any]):
            self.reco_id = reco_id
            self.visu_pars = _Params(visu_pars)
            self.reco = _Params(reco)

    class _Scan:
        def __init__(self, method: Dict[str, Any], acqp: Dict[str, Any], recos: Dict[int, _Reco]):
            self.method = _Params(method)
            self.acqp = _Params(acqp)
            self._recos = recos

        def get_reco(self, reco_id: int) -> _Reco:
            return self._recos[reco_id]

    spec_yaml = (
        "out.scalar:\n"
        "  sources:\n"
        "    - file: method\n"
        "      key: PVM_SPackArrNSlices\n"
        "out.const_value:\n"
        "  inputs:\n"
        "    foo:\n"
        "      const: 42\n"
        "  transform: pick_foo\n"
        "out.combined:\n"
        "  inputs:\n"
        "    a:\n"
        "      sources:\n"
        "        - file: acqp\n"
        "          key: ACQ_scan_name\n"
        "    b:\n"
        "      sources:\n"
        "        - file: visu_pars\n"
        "          key: VisuCoreFrameCount\n"
        "          reco_id: 1\n"
        "      default: 1\n"
        "  transform: join_fields\n"
    )

    transforms_py = (
        "def pick_foo(foo):\n"
        "    return foo\n"
        "\n"
        "def join_fields(a, b):\n"
        "    return f\"{a}_{b}\"\n"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        spec_path = Path(tmpdir) / "spec.yaml"
        transforms_path = Path(tmpdir) / "transforms.py"
        spec_path.write_text(
            "__meta__:\n"
            "  transforms_source: \"transforms.py\"\n"
            f"{spec_yaml}",
            encoding="utf-8",
        )
        transforms_path.write_text(transforms_py, encoding="utf-8")
        spec, transforms = load_spec(
            spec_path,
        )

    scan = _Scan(
        method={"PVM_SPackArrNSlices": 8},
        acqp={"ACQ_scan_name": "test_scan"},
        recos={
            1: _Reco(
                reco_id=1,
                visu_pars={"VisuCoreFrameCount": 3},
                reco={},
            )
        },
    )

    result = map_parameters(scan, spec, transforms)
    print(result)
