# Mypy extension for Visual Studio Code

A Visual Studio Code extension with support for the Mypy type checker. This extension ships with `mypy=1.5.1`.

> **Note**: The minimum version of Mypy this extension supports is `1.0.0`.

This extension supports all [actively supported versions](https://devguide.python.org/#status-of-python-branches) of the Python language (i.e., Python >= 3.8).

For more information on Mypy, see https://www.mypy-lang.org/.

## Usage and Features

The Mypy extension provides a series of features to help your productivity while working with Python code in Visual Studio Code. Check out the [Settings section](#settings) for more details on how to customize the extension.

-   **Integrated type checking**: Once this extension is installed in Visual Studio Code, Mypy will be automatically executed when you open a Python file, reporting any errors or warnings in the "Problems" window.
-   **Customizable Mypy version**: By default, this extension uses the version of Mypy that is shipped with the extension. However, you can configure it to use a different binary installed in your environment through the `mypy-type-checker.importStrategy` setting, or set it to a custom Mypy executable through the `mypy-type-checker.path` settings.
-   **Workspace-wide type checking**: By default, this extension will only report errors and warnings for files open in the editor. However, you can configure it to report errors and warnings for the entire workspace through the `mypy-type-checker.reportingScope` setting.
-   **Mono repo support**: If you are working with a mono repo, you can configure the extension offer type checking for Python files in subfolders of the workspace root folder by setting the `mypy-type-checker.cwd` setting to `${fileDirname}`. You can also set it to ignore/skip type checking for certain files or folder paths by specifying a glob pattern to the `mypy-type-checker.ignorePatterns` setting.
-   **Customizable linting rules**: You can customize the severity of specific Mypy error codes through the `mypy-type-checker.severity` setting.
-   **Mypy Daemon support**: This extension supports the Mypy daemon (`dmypy`) for faster type checking when the reporting scope is set to the entire workspace. To enable it, set the `mypy-type-checker.preferDaemon` setting to `true`.

### Disabling Mypy

You can skip type checking with Mypy for specific files or directories by setting the `mypy-type-checker.ignorePatterns` setting.

If you wish to disable Mypy for your entire workspace or globally, you can [disable this extension](https://code.visualstudio.com/docs/editor/extension-marketplace#_disable-an-extension) in Visual Studio Code.


## Settings

There are several settings you can configure to customize the behavior of this extension.

| Settings                         | Default                                       | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| mypy-type-checker.args           | `[]`                                          | Arguments passed to Mypy to enable type checking on Python files. Each argument should be provided as a separate string in the array. <br> Example: <br> `"mypy-type-checker.args" = ["--config-file=<file>"]`                                                                                                                                                                                                                                                                                                                                                                                                                |
| mypy-type-checker.severity       | `{ "error": "Error", "note": "Information" }` | Mapping of Mypy's message types to VS Code's diagnostic severity levels as displayed in the Problems window. You can also use it to override specific Mypy error codes. <br>For example: `{ "error": "Error", "note": "Information", "name-defined": "Warning" }`                                                                                                                                                                                                                                                                                                                                                             |
| mypy-type-checker.path           | `[]`                                          | Path or command to be used by the extension to type check Python files with Mypy. Accepts an array of a single or multiple strings. If passing a command, each argument should be provided as a separate string in the array. If set to `["mypy"]`, it will use the version of Mypy available in the `PATH` environment variable. Note: Using this option may slowdown type checking. <br> Examples: <br>- `["~/global_env/mypy"]` <br>- `["conda", "run", "-n", "lint_env", "python", "-m", "mypy"]`                                                                                                                         |
| mypy-type-checker.interpreter    | `[]`                                          | Path to a Python executable or a command that will be used to launch the Mypy server and any subprocess. Accepts an array of a single or multiple strings. When set to `[]`, the extension will use the path to the selected Python interpreter. If passing a command, each argument should be provided as a separate string in the array.                                                                                                                                                                                                                                                                                    |
| mypy-type-checker.importStrategy | `useBundled`                                  | Defines which Mypy binary to be used to type check Python files. When set to `useBundled`, the extension will use the Mypy binary that is shipped with the extension. When set to `fromEnvironment`, the extension will attempt to use the Mypy binary and all dependencies that are available in the currently selected environment. Note: If the extension can't find a valid Mypy binary in the selected environment, it will fallback to using the Mypy binary that is shipped with the extension. Note: The `mypy-type-checker.path` setting takes precedence and overrides the behavior of `mypy-type-checker.importStrategy`. |

| mypy-type-checker.showNotifications | `off` | Controls when notifications are shown by this extension. Accepted values are `onError`, `onWarning`, `always` and `off`. |

| mypy-type-checker.reportingScope | `file` | (experimental) Controls the scope of Mypy's problem reporting. If set to `file`, Mypy will limit its problem reporting to the files currently open in the editor. If set to `workspace``, Mypy will extend its problem reporting to include all files within the workspace.                                                                                                                                                                                                                                                                                                                                                   |
| mypy-type-checker.preferDaemon      | true                                          | (experimental) Whether the Mypy daemon (`dmypy`) will take precedence over `mypy`for type checking. Note: if `mypy-type-checker.reportingScope`is set to `workspace`, enabling the Mypy daemon will offer a faster type checking experience. This setting will be overridden if `mypy-type-checker.path`is set.                                                                                                                                                                                                                                                                                                            |
| mypy-type-checker.ignorePatterns    |`[]` | Configure [glob patterns](https://code.visualstudio.com/docs/editor/glob-patterns) to exclude files or folders from being type checked by Mypy. |

The following variables are supported for substitution in the `mypy-type-checker.args`, `mypy-type-checker.cwd`, `mypy-type-checker.path`, `mypy-type-checker.interpreter` and `mypy-type-checker.ignorePatterns` settings:

-   `${workspaceFolder}`
-   `${workspaceFolder:FolderName}`
-   `${userHome}`
-   `${env:EnvVarName}`

The `mypy-type-checker.path` setting also supports the `${interpreter}` variable as one of the entries of the array. This variable is subtituted based on the value of the `mypy-type-checker.interpreter` setting.

## Commands

| Command              | Description                       |
| -------------------- | --------------------------------- |
| Mypy: Restart Server | Force re-start the linter server. |

## Logging

From the Command Palette (**View** > **Command Palette ...**), run the **Developer: Set Log Level...** command. Select **Mypy Type Checker** from the **Extension logs** group. Then select the log level you want to set.

Alternatively, you can set the `mypy-type-checker.trace.server` setting to `verbose` to get more detailed logs from the Mypy server. This can be helpful when filing bug reports.

To open the logs, click on the language status icon (`{}`) on the bottom right of the Status bar, next to the Python language mode. Locate the **Mypy Type Checker** entry and select **Open logs**.

## Troubleshooting

In this section, you will find some common issues you might encounter and how to resolve them. If you are experiencing any issues that are not covered here, please [file an issue](https://github.com/microsoft/vscode-mypy/issues).

-   If the `mypy-type-checker.importStrategy` setting is set to `fromEnvironment` but Mypy is not found in the selected environment, this extension will fallback to using the Mypy binary that is shipped with the extension. However, if there are dependencies installed in the environment, those dependencies will be used along with the shipped Mypy binary. This can lead to problems if the dependencies are not compatible with the shipped Mypy binary.

    To resolve this issue, you can:

    -   Set the `mypy-type-checker.importStrategy` setting to `useBundled` and the `mypy-type-checker.path` setting to point to the custom binary of Mypy you want to use; or
    -   Install Mypy in the selected environment.

-   If you have the reporting scope set to `workspace` and notice a slowdown in type checking, you can try enabling the Mypy daemon (`dmypy`) by setting the `mypy-type-checker.preferDaemon` setting to `true`.
