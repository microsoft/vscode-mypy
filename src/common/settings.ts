// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Extension-specific settings: ISettings type extension and legacy settings logging.
// All shared settings resolution is handled by @vscode/common-python-lsp directly.

import {
    IBaseSettings,
    getConfiguration,
    getWorkspaceFolders,
    logLegacySettings as _logLegacySettings,
    traceWarn,
} from '@vscode/common-python-lsp';

export interface ISettings extends IBaseSettings {
    ignorePatterns: string[];
    extraPaths: string[];
    reportingScope: string;
    preferDaemon: boolean;
    severity: Record<string, string>;
}

export function logLegacySettings(): void {
    // Handle mypyEnabled separately — it has custom messaging not covered
    // by the shared helper's simple "use X instead" pattern.
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
        } catch (err) {
            traceWarn(`Error while logging legacy settings: ${err}`);
        }
    });

    // Standard legacy key → new key mappings handled by the shared helper.
    _logLegacySettings('mypy-type-checker', [
        { legacyKey: 'linting.cwd', newKey: 'cwd' },
        { legacyKey: 'linting.mypyArgs', newKey: 'args', isArray: true },
        { legacyKey: 'linting.mypyPath', newKey: 'path' },
    ]);
}
