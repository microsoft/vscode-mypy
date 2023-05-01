# Mypy extension for Visual Studio Code

A Visual Studio Code extension with support for the `mypy` linter. The extension ships with `mypy=1.1.1`.

For more information on `mypy`, see https://www.mypy-lang.org/.

Note:

-   This extension is supported for all [actively supported versions](https://devguide.python.org/#status-of-python-branches) of the `python` language (i.e., python >= 3.7).
-   Minimum supported version of `mypy` is `1.0.0`.

## Usage

Once installed in Visual Studio Code, mypy will be automatically executed when you open a Python file.

If you want to disable mypy, you can [disable this extension](https://code.visualstudio.com/docs/editor/extension-marketplace#_disable-an-extension) per workspace in Visual Studio Code.

## Settings

| Settings              | Default                                       | Description                                                                                                                                                                                                                                                       |
| --------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| mypy.args             | `[]`                                          | Custom arguments passed to `mypy`. E.g `"mypy.args" = ["--config-file=<file>"]`                                                                                                                                                                                   |
| mypy.severity         | `{ "error": "Error", "note": "Information" }` | Controls mapping of severity from `mypy` to VS Code severity when displaying in the problems window. You can override specific `mypy` error codes `{ "error": "Error", "note": "Information", "name-defined": "Warning" }`                                        |
| mypy.path             | `[]`                                          | Setting to provide custom `mypy` executable. This will slow down linting, since we will have to run `mypy` executable every time or file save or open. Example 1: `["~/global_env/mypy"]` Example 2: `["conda", "run", "-n", "lint_env", "python", "-m", "mypy"]` |
| mypy.interpreter      | `[]`                                          | Path to a python interpreter to use to run the linter server.                                                                                                                                                                                                     |
| mypy.importStrategy   | `useBundled`                                  | Setting to choose where to load `mypy` from. `useBundled` picks mypy bundled with the extension. `fromEnvironment` uses `mypy` available in the environment.                                                                                                      |
| mypy.showNotification | `off`                                         | Setting to control when a notification is shown.                                                                                                                                                                                                                  |

## Commands

| Command              | Description                       |
| -------------------- | --------------------------------- |
| Mypy: Restart Server | Force re-start the linter server. |

## Logging

From the command palette (View > Command Palette ...), run the `Developer: Set Log Level...` command. From the quick pick menu, select `Mypy` extension from the `Extension logs` group. Then select the log level you want to set.
