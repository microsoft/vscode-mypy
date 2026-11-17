Please see [our wiki](https://github.com/microsoft/vscode-mypy/wiki/Contributing-Guide) on how to contribute to this project.

## Shared runtime checkout

Initialize submodules with `git submodule update --init --recursive`, then use
the Node version in `.nvmrc` and run `npm run setup` (or `npm run setup:msft` for
the Microsoft feeds). `npm ci` installs the pinned shared checkout's locked
TypeScript dependencies and builds its public `typescript/dist` entry point.
Compile, test compilation, watch startup and packaging rebuild that entry point;
an existing `dist` is not treated as proof that the checkout has been built.
There is no shared-runtime registry dependency or bare-module alias.

The native nox install and setup/build-package sessions install the Python
runtime from `external/vscode-common-python-lsp/python` into `bundled/libs`,
from the same gitlink as the TypeScript runtime. Keep both halves together when
updating the submodule. The Python import remains `vscode_common_python_lsp`;
`vscode-python-tool-internal` is private checkout metadata, not a registry
dependency.

Activation delegates common lifecycle ownership to `activateToolExtension`.
Legacy-setting warnings remain extension-owned; daemon selection, status-file
handling and per-document `${nearestConfig}` resolution remain in the Python
server. No custom launch hooks are needed by Mypy.

The gitlink pins `664672c16ce7848f09442ce0e301279a199ceb08`, the merged revision
of [shared PR #151](https://github.com/microsoft/vscode-common-python-lsp/pull/151).
Validation builds both runtime halves from this exact checkout. When updating
the gitlink, rebuild and rerun the native build and tests.
