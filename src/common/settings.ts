// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Extension-specific settings: ISettings type extension and legacy settings logging.
// All shared settings resolution is handled by @vscode/common-python-lsp directly.

import { IBaseSettings, getConfiguration, getWorkspaceFolders, traceWarn } from '@vscode/common-python-lsp';

export interface ISettings extends IBaseSettings {
    ignorePatterns: string[];
    extraPaths: string[];
    reportingScope: string;
    preferDaemon: boolean;
    severity: Record<string, string>;
}

export function logLegacySettings(): void {
    getWorkspaceFolders().forEach((workspace) => {
        try {
            const legacyConfig = getConfiguration('python', workspace.uri);

            const legacyMypyEnabled = legacyConfig.get<boolean>('linting.mypyEnabled', false);
            if (legacyMypyEnabled) {
                traceWarn(`"python.linting.mypyEnabled" is deprecated. You can remove that setting.`);
                traceWarn(
                    'The mypy extension is always enabled. However, you can disable it per workspace using the extensions view.',
                );
                traceWarn('You can exclude files and folders using the `python.linting.ignorePatterns` setting.');
                traceWarn(
                    `"python.linting.mypyEnabled" value for workspace ${workspace.uri.fsPath}: ${legacyMypyEnabled}`,
                );
            }

            const legacyCwd = legacyConfig.get<string>('linting.cwd');
            if (legacyCwd) {
                traceWarn(`"python.linting.cwd" is deprecated. Use "mypy-type-checker.cwd" instead.`);
                traceWarn(`"python.linting.cwd" value for workspace ${workspace.uri.fsPath}: ${legacyCwd}`);
            }

            const legacyArgs = legacyConfig.get<string[]>('linting.mypyArgs', []);
            if (legacyArgs.length > 0) {
                traceWarn(`"python.linting.mypyArgs" is deprecated. Use "mypy-type-checker.args" instead.`);
                traceWarn(`"python.linting.mypyArgs" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyArgs, null, 4)}`);
            }

            const legacyPath = legacyConfig.get<string>('linting.mypyPath', '');
            if (legacyPath.length > 0 && legacyPath !== 'mypy') {
                traceWarn(`"python.linting.mypyPath" is deprecated. Use "mypy-type-checker.path" instead.`);
                traceWarn(`"python.linting.mypyPath" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyPath, null, 4)}`);
            }
        } catch (err) {
            traceWarn(`Error while logging legacy settings: ${err}`);
        }
    });
}
