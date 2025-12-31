# Python API

Examples below show common patterns when using BrkRaw as a library.

## Load a dataset

```python
import brkraw as brk

loader = brk.load("/path/to/study")
```

## Inspect info

```python
info = loader.info(scope="full", as_dict=True)
print(info["Study"])
```

## Read scan data

```python
scan = loader.get_scan(3)
data = scan.get_dataobj(reco_id=1)
```

## Build a NIfTI image

```python
nii = loader.get_nifti1image(3, reco_id=1)
if isinstance(nii, tuple):
    # Multiple slice packs
    for i, img in enumerate(nii, start=1):
        img.to_filename(f"scan3_slpack{i}.nii.gz")
else:
    nii.to_filename("scan3.nii.gz")
```

## Read metadata (sidecar)

```python
meta = loader.get_metadata(3, reco_id=1)
print(meta)
```

## Parameter search

```python
params = loader.search_params("PVM_RepetitionTime", scan_id=3)
print(params)
```
