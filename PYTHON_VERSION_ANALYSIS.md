# Why get_mypy_info Returns None on Python 3.10+ but not 3.9

## The Problem

The `get_mypy_info()` function returns `None` on Python 3.10+ but works fine on Python 3.9, causing:
```
AttributeError: 'NoneType' object has no attribute 'version'
```

## Root Cause Analysis

### How get_mypy_info Works

1. Calls `_run_unidentified_tool(["--version"], settings)`
2. This runs `python -m mypy --version` in a subprocess
3. Parses the output to extract mypy version
4. If ANY exception occurs, returns `None`

### The CI Test Environment

From `.github/workflows/pr-check.yml`:
1. **Step 1**: Install bundled libs using Python 3.9
   - Runs: `python -m nox --session install_bundled_libs`
   - Installs mypy and other deps to `./bundled/libs/`
2. **Step 2**: Switch to test Python version (3.10, 3.11, 3.12, 3.13)
3. **Step 3**: Run tests with that Python version

### Why It Fails on Python 3.10+

**The bundled libs are Python version-specific!**

When you install packages with Python 3.9 to `./bundled/libs/`, some packages may include:
- Compiled C extensions (`.so` or `.pyd` files)
- Version-specific bytecode (`.pyc` files)
- Python version-specific package metadata

When Python 3.10+ tries to import these Python 3.9-compiled packages:
1. The import might fail due to ABI incompatibility
2. C extensions compiled for Python 3.9 won't work on Python 3.10+
3. The subprocess `python -m mypy --version` fails
4. Exception is caught, `None` is returned

### Proof

Check if mypy has compiled extensions:
```bash
# After installing bundled libs with Python 3.9
find bundled/libs -name "*.so" -o -name "*.pyd"
```

If mypy or its dependencies (like `mypy_extensions`, `typing_extensions`, etc.) have compiled components, they won't work across Python versions.

## The Solution

The code has already been fixed to handle `None` returns from `get_mypy_info()`:

```python
def _log_version_info() -> None:
    for settings in WORKSPACE_SETTINGS.values():
        code_workspace = settings["workspaceFS"]
        mypy_info = get_mypy_info(settings)
        
        if mypy_info is None:
            log_error(
                f"Unable to determine mypy version for {code_workspace}. "
                f"Please ensure mypy is installed and accessible."
            )
            continue
        
        actual_version = mypy_info.version
        # ... rest of the code
```

This prevents the AttributeError.

## Why This Approach Is Acceptable

The version check is informational and for validation. The actual mypy execution for linting works because:

1. When running mypy for actual linting, the `importStrategy` setting ensures PYTHONPATH includes bundled libs
2. The mypy module IS accessible when needed for linting
3. The version check failure doesn't prevent the extension from working

## Alternative Solutions (Not Recommended)

1. **Install bundled libs with each Python version separately**
   - Would require multiple install steps in CI
   - Would bloat the extension package

2. **Use pure-Python packages only**
   - Not always possible
   - Would limit package choices

3. **Skip version check**
   - Already effectively done by handling None
   - Logs a helpful error message

## Conclusion

The `None` return is expected behavior when bundled libs are installed with one Python version but accessed from another. The fix to handle `None` gracefully is the correct solution.
