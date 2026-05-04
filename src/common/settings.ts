// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { ConfigurationChangeEvent, WorkspaceFolder } from 'vscode';
import {
    IBaseSettings,
    checkIfConfigurationChanged as _checkIfConfigurationChanged,
    getGlobalSettings as _getGlobalSettings,
    getWorkspaceSettings as _getWorkspaceSettings,
    resolveVariables,
} from '@vscode/common-python-lsp';
import { MYPY_TOOL_CONFIG } from './constants';
import { getInterpreterDetails } from './python';
import { getConfiguration, getWorkspaceFolders } from './vscodeapi';
import { traceWarn } from './logging';

export interface ISettings extends IBaseSettings {
    ignorePatterns: string[];
    extraPaths: string[];
    reportingScope: string;
    preferDaemon: boolean;
    severity: Record<string, string>;
}

export function getExtensionSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings[]> {
    return Promise.all(getWorkspaceFolders().map((w) => getWorkspaceSettings(namespace, w, includeInterpreter)));
}

export async function getWorkspaceSettings(
    namespace: string,
    workspace: WorkspaceFolder,
    includeInterpreter?: boolean,
): Promise<ISettings> {
    const resolveInterpreter = includeInterpreter ? getInterpreterDetails : undefined;
    const settings = (await _getWorkspaceSettings(
        namespace,
        workspace,
        MYPY_TOOL_CONFIG,
        resolveInterpreter,
    )) as ISettings;
    if (settings.ignorePatterns?.length > 0) {
        settings.ignorePatterns = resolveVariables(settings.ignorePatterns, workspace);
    }
    return settings;
}

export async function getGlobalSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings> {
    const resolveInterpreter = includeInterpreter ? async () => getInterpreterDetails() : undefined;
    const settings = (await _getGlobalSettings(namespace, MYPY_TOOL_CONFIG, resolveInterpreter)) as ISettings;
    if (!includeInterpreter) {
        settings.interpreter = [];
    }
    return settings;
}

export function checkIfConfigurationChanged(e: ConfigurationChangeEvent, namespace: string): boolean {
    return _checkIfConfigurationChanged(e, namespace, MYPY_TOOL_CONFIG.trackedSettings);
}

export function logLegacySettings(namespace: string): void {
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
                traceWarn(`"python.linting.cwd" is deprecated. Use "${namespace}.cwd" instead.`);
                traceWarn(`"python.linting.cwd" value for workspace ${workspace.uri.fsPath}: ${legacyCwd}`);
            }

            const legacyArgs = legacyConfig.get<string[]>('linting.mypyArgs', []);
            if (legacyArgs.length > 0) {
                traceWarn(`"python.linting.mypyArgs" is deprecated. Use "${namespace}.args" instead.`);
                traceWarn(`"python.linting.mypyArgs" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyArgs, null, 4)}`);
            }

            const legacyPath = legacyConfig.get<string>('linting.mypyPath', '');
            if (legacyPath.length > 0 && legacyPath !== 'mypy') {
                traceWarn(`"python.linting.mypyPath" is deprecated. Use "${namespace}.path" instead.`);
                traceWarn(`"python.linting.mypyPath" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyPath, null, 4)}`);
            }
        } catch (err) {
            traceWarn(`Error while logging legacy settings: ${err}`);
        }
    });
}
