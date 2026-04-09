// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { Disposable, workspace } from 'vscode';
import { MYPY_CONFIG_FILES } from './constants';
import { traceError, traceLog } from './logging';

export function createConfigFileWatchers(onConfigChanged: () => Promise<void>): Disposable[] {
    return MYPY_CONFIG_FILES.map((pattern) => {
        const watcher = workspace.createFileSystemWatcher(`**/${pattern}`);
        let disposed = false;
        let pending: Promise<void> | undefined;

        const handleEvent = (event: string) => {
            if (disposed) {
                return;
            }
            traceLog(`Mypy config file ${event}: ${pattern}`);
            pending = onConfigChanged()
                .catch((e) => traceError(`Config file ${event} handler failed`, e))
                .finally(() => {
                    pending = undefined;
                });
        };

        const changeDisposable = watcher.onDidChange(() => handleEvent('changed'));
        const createDisposable = watcher.onDidCreate(() => handleEvent('created'));
        const deleteDisposable = watcher.onDidDelete(() => handleEvent('deleted'));

        return {
            dispose(): void {
                disposed = true;
                pending = undefined;
                changeDisposable.dispose();
                createDisposable.dispose();
                deleteDisposable.dispose();
                watcher.dispose();
            },
        };
    });
}
