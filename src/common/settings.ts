// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { ConfigurationChangeEvent, ConfigurationScope, WorkspaceConfiguration, WorkspaceFolder } from 'vscode';
import { getInterpreterDetails } from './python';
import { getConfiguration, getWorkspaceFolders } from './vscodeapi';
import { traceLog } from './logging';

const DEFAULT_SEVERITY: Record<string, string> = {
    error: 'Error',
    note: 'Information',
};

export interface ISettings {
    cwd: string;
    workspace: string;
    args: string[];
    severity: Record<string, string>;
    path: string[];
    interpreter: string[];
    importStrategy: string;
    showNotifications: string;
    extraPaths: string[];
    reportingScope: string;
}

export function getExtensionSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings[]> {
    return Promise.all(getWorkspaceFolders().map((w) => getWorkspaceSettings(namespace, w, includeInterpreter)));
}

function resolveVariables(value: string[], workspace?: WorkspaceFolder): string[] {
    const substitutions = new Map<string, string>();
    const home = process.env.HOME || process.env.USERPROFILE;
    if (home) {
        substitutions.set('${userHome}', home);
    }
    if (workspace) {
        substitutions.set('${workspaceFolder}', workspace.uri.fsPath);
    }
    substitutions.set('${cwd}', process.cwd());
    getWorkspaceFolders().forEach((w) => {
        substitutions.set('${workspaceFolder:' + w.name + '}', w.uri.fsPath);
    });

    return value.map((s) => {
        for (const [key, value] of substitutions) {
            s = s.replace(key, value);
        }
        return s;
    });
}

function getArgs(namespace: string, workspace: WorkspaceFolder): string[] {
    const config = getConfiguration(namespace, workspace.uri);
    const args = config.get<string[]>('args', []);

    if (args.length > 0) {
        return args;
    }

    const legacyConfig = getConfiguration('python', workspace.uri);
    const legacyArgs = legacyConfig.get<string[]>('linting.mypyArgs', []);
    if (legacyArgs.length > 0) {
        traceLog(`Using legacy Mypy args from 'python.linting.mypyArgs': ${legacyArgs.join(' ')}.`);
        return legacyArgs;
    }

    return [];
}

function getPath(namespace: string, workspace: WorkspaceFolder): string[] {
    const config = getConfiguration(namespace, workspace.uri);
    const path = config.get<string[]>('path', []);

    if (path.length > 0) {
        return path;
    }

    const legacyConfig = getConfiguration('python', workspace.uri);
    const legacyPath = legacyConfig.get<string>('linting.mypyPath', '');
    if (legacyPath.length > 0 && legacyPath !== 'mypy') {
        traceLog(`Using legacy Mypy path from 'python.linting.mypyPath': ${legacyPath}`);
        return [legacyPath];
    }
    return [];
}

function getCwd(namespace: string, workspace: WorkspaceFolder): string {
    const legacyConfig = getConfiguration('python', workspace.uri);
    const legacyCwd = legacyConfig.get<string>('linting.cwd');

    if (legacyCwd) {
        traceLog('Using cwd from `python.linting.cwd`.');
        return resolveVariables([legacyCwd], workspace)[0];
    }

    return workspace.uri.fsPath;
}

function getExtraPaths(namespace: string, workspace: WorkspaceFolder): string[] {
    const legacyConfig = getConfiguration('python', workspace.uri);
    const legacyExtraPaths = legacyConfig.get<string[]>('analysis.extraPaths', []);

    if (legacyExtraPaths.length > 0) {
        traceLog('Using cwd from `python.analysis.extraPaths`.');
    }
    return legacyExtraPaths;
}

export function getInterpreterFromSetting(namespace: string, scope?: ConfigurationScope) {
    const config = getConfiguration(namespace, scope);
    return config.get<string[]>('interpreter');
}

export async function getWorkspaceSettings(
    namespace: string,
    workspace: WorkspaceFolder,
    includeInterpreter?: boolean,
): Promise<ISettings> {
    const config = getConfiguration(namespace, workspace.uri);

    let interpreter: string[] = [];
    if (includeInterpreter) {
        interpreter = getInterpreterFromSetting(namespace, workspace) ?? [];
        if (interpreter.length === 0) {
            traceLog(`No interpreter found from setting ${namespace}.interpreter`);
            traceLog(`Getting interpreter from ms-python.python extension for workspace ${workspace.uri.fsPath}`);
            interpreter = (await getInterpreterDetails(workspace.uri)).path ?? [];
            if (interpreter.length > 0) {
                traceLog(
                    `Interpreter from ms-python.python extension for ${workspace.uri.fsPath}:`,
                    `${interpreter.join(' ')}`,
                );
            }
        } else {
            traceLog(`Interpreter from setting ${namespace}.interpreter: ${interpreter.join(' ')}`);
        }

        if (interpreter.length === 0) {
            traceLog(`No interpreter found for ${workspace.uri.fsPath} in settings or from ms-python.python extension`);
        }
    }

    const args = getArgs(namespace, workspace);
    const mypyPath = getPath(namespace, workspace);
    const extraPaths = getExtraPaths(namespace, workspace);
    const workspaceSetting = {
        cwd: getCwd(namespace, workspace),
        workspace: workspace.uri.toString(),
        args: resolveVariables(args, workspace),
        severity: config.get<Record<string, string>>('severity', DEFAULT_SEVERITY),
        path: resolveVariables(mypyPath, workspace),
        interpreter: resolveVariables(interpreter, workspace),
        importStrategy: config.get<string>('importStrategy', 'useBundled'),
        showNotifications: config.get<string>('showNotifications', 'off'),
        extraPaths: resolveVariables(extraPaths, workspace),
        reportingScope: config.get<string>('reportingScope', 'file'),
    };
    return workspaceSetting;
}

function getGlobalValue<T>(config: WorkspaceConfiguration, key: string, defaultValue: T): T {
    const inspect = config.inspect<T>(key);
    return inspect?.globalValue ?? inspect?.defaultValue ?? defaultValue;
}

export async function getGlobalSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings> {
    const config = getConfiguration(namespace);

    let interpreter: string[] = [];
    if (includeInterpreter) {
        interpreter = getGlobalValue<string[]>(config, 'interpreter', []);
        if (interpreter === undefined || interpreter.length === 0) {
            interpreter = (await getInterpreterDetails()).path ?? [];
        }
    }

    const setting = {
        cwd: process.cwd(),
        workspace: process.cwd(),
        args: getGlobalValue<string[]>(config, 'args', []),
        severity: getGlobalValue<Record<string, string>>(config, 'severity', DEFAULT_SEVERITY),
        path: getGlobalValue<string[]>(config, 'path', []),
        interpreter: interpreter ?? [],
        importStrategy: getGlobalValue<string>(config, 'importStrategy', 'useBundled'),
        showNotifications: getGlobalValue<string>(config, 'showNotifications', 'off'),
        extraPaths: getGlobalValue<string[]>(config, 'extraPaths', []),
        reportingScope: config.get<string>('reportingScope', 'file'),
    };
    return setting;
}

export function checkIfConfigurationChanged(e: ConfigurationChangeEvent, namespace: string): boolean {
    const settings = [
        `${namespace}.args`,
        `${namespace}.severity`,
        `${namespace}.path`,
        `${namespace}.interpreter`,
        `${namespace}.importStrategy`,
        `${namespace}.showNotifications`,
    ];
    const changed = settings.map((s) => e.affectsConfiguration(s));
    return changed.includes(true);
}
