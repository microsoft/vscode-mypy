// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { ConfigurationChangeEvent, ConfigurationScope, WorkspaceConfiguration, WorkspaceFolder } from 'vscode';
import { traceLog, traceWarn } from './logging';
import { getInterpreterDetails } from './python';
import { getConfiguration, getWorkspaceFolders } from './vscodeapi';

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
    ignorePatterns: string[];
    interpreter: string[];
    importStrategy: string;
    showNotifications: string;
    extraPaths: string[];
    reportingScope: string;
    preferDaemon: boolean;
}

export function getExtensionSettings(namespace: string, includeInterpreter?: boolean): Promise<ISettings[]> {
    return Promise.all(getWorkspaceFolders().map((w) => getWorkspaceSettings(namespace, w, includeInterpreter)));
}

function resolveVariables(
    value: string[],
    workspace?: WorkspaceFolder,
    interpreter?: string[],
    env?: NodeJS.ProcessEnv,
): string[] {
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

    env = env || process.env;
    if (env) {
        for (const [key, value] of Object.entries(env)) {
            if (value) {
                substitutions.set('${env:' + key + '}', value);
            }
        }
    }

    const modifiedValue = [];
    for (const v of value) {
        if (interpreter && v === '${interpreter}') {
            modifiedValue.push(...interpreter);
        } else {
            modifiedValue.push(v);
        }
    }

    return modifiedValue.map((s) => {
        for (const [key, value] of substitutions) {
            s = s.replace(key, value);
        }
        return s;
    });
}

function getCwd(config: WorkspaceConfiguration, workspace: WorkspaceFolder): string {
    const cwd = config.get<string>('cwd', workspace.uri.fsPath);
    return resolveVariables([cwd], workspace)[0];
}

function getExtraPaths(_namespace: string, workspace: WorkspaceFolder): string[] {
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
    const config = getConfiguration(namespace, workspace);

    let interpreter: string[] = [];
    if (includeInterpreter) {
        interpreter = getInterpreterFromSetting(namespace, workspace) ?? [];
        if (interpreter.length === 0) {
            interpreter = (await getInterpreterDetails(workspace.uri)).path ?? [];
        }
    }

    const extraPaths = getExtraPaths(namespace, workspace);
    const workspaceSetting = {
        cwd: getCwd(config, workspace),
        workspace: workspace.uri.toString(),
        args: resolveVariables(config.get<string[]>('args', []), workspace),
        severity: config.get<Record<string, string>>('severity', DEFAULT_SEVERITY),
        path: resolveVariables(config.get<string[]>('path', []), workspace, interpreter),
        ignorePatterns: resolveVariables(config.get<string[]>('ignorePatterns', []), workspace),
        interpreter: resolveVariables(interpreter, workspace),
        importStrategy: config.get<string>('importStrategy', 'useBundled'),
        showNotifications: config.get<string>('showNotifications', 'off'),
        extraPaths: resolveVariables(extraPaths, workspace),
        reportingScope: config.get<string>('reportingScope', 'file'),
        preferDaemon: config.get<boolean>('preferDaemon', true),
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
        cwd: getGlobalValue<string>(config, 'cwd', process.cwd()),
        workspace: process.cwd(),
        args: getGlobalValue<string[]>(config, 'args', []),
        severity: getGlobalValue<Record<string, string>>(config, 'severity', DEFAULT_SEVERITY),
        path: getGlobalValue<string[]>(config, 'path', []),
        ignorePatterns: getGlobalValue<string[]>(config, 'ignorePatterns', []),
        interpreter: interpreter ?? [],
        importStrategy: getGlobalValue<string>(config, 'importStrategy', 'useBundled'),
        showNotifications: getGlobalValue<string>(config, 'showNotifications', 'off'),
        extraPaths: getGlobalValue<string[]>(config, 'extraPaths', []),
        reportingScope: config.get<string>('reportingScope', 'file'),
        preferDaemon: config.get<boolean>('preferDaemon', true),
    };
    return setting;
}

export function checkIfConfigurationChanged(e: ConfigurationChangeEvent, namespace: string): boolean {
    const settings = [
        `${namespace}.args`,
        `${namespace}.cwd`,
        `${namespace}.severity`,
        `${namespace}.path`,
        `${namespace}.interpreter`,
        `${namespace}.importStrategy`,
        `${namespace}.showNotifications`,
        `${namespace}.reportingScope`,
        `${namespace}.preferDaemon`,
        `${namespace}.ignorePatterns`,
        'python.analysis.extraPaths',
    ];
    const changed = settings.map((s) => e.affectsConfiguration(s));
    return changed.includes(true);
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
