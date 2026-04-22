// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as sinon from 'sinon';
import { workspace } from 'vscode';
import { createConfigFileWatchers } from '../../../../common/configWatcher';
import { MYPY_CONFIG_FILES } from '../../../../common/constants';

suite('Config File Watcher Tests', () => {
    let createFileSystemWatcherStub: sinon.SinonStub;
    let mockWatcher: {
        onDidChange: sinon.SinonStub;
        onDidCreate: sinon.SinonStub;
        onDidDelete: sinon.SinonStub;
        dispose: sinon.SinonStub;
    };
    let changeDisposable: { dispose: sinon.SinonStub };
    let createDisposable: { dispose: sinon.SinonStub };
    let deleteDisposable: { dispose: sinon.SinonStub };
    let onConfigChangedCallback: sinon.SinonStub;

    setup(() => {
        changeDisposable = { dispose: sinon.stub() };
        createDisposable = { dispose: sinon.stub() };
        deleteDisposable = { dispose: sinon.stub() };

        mockWatcher = {
            onDidChange: sinon.stub().returns(changeDisposable),
            onDidCreate: sinon.stub().returns(createDisposable),
            onDidDelete: sinon.stub().returns(deleteDisposable),
            dispose: sinon.stub(),
        };

        createFileSystemWatcherStub = sinon.stub(workspace, 'createFileSystemWatcher');
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        createFileSystemWatcherStub.returns(mockWatcher as any);

        onConfigChangedCallback = sinon.stub().resolves();
    });

    teardown(() => {
        sinon.restore();
    });

    test('Creates a file watcher for each mypy config file pattern', () => {
        createConfigFileWatchers(onConfigChangedCallback);

        assert.strictEqual(createFileSystemWatcherStub.callCount, MYPY_CONFIG_FILES.length);
        for (let i = 0; i < MYPY_CONFIG_FILES.length; i++) {
            assert.isTrue(
                createFileSystemWatcherStub.getCall(i).calledWith(`**/${MYPY_CONFIG_FILES[i]}`),
                `Expected watcher for pattern **/${MYPY_CONFIG_FILES[i]}`,
            );
        }
    });

    test('Server restarts when a config file is created', async () => {
        createConfigFileWatchers(onConfigChangedCallback);

        const createHandler = mockWatcher.onDidCreate.getCall(0).args[0];
        await createHandler();

        assert.isTrue(
            onConfigChangedCallback.calledOnce,
            'Expected onConfigChanged to be called when config file is created',
        );
    });

    test('Server restarts when a config file is changed', async () => {
        createConfigFileWatchers(onConfigChangedCallback);

        // Simulate modifying pyproject.toml (index 2)
        const changeHandler = mockWatcher.onDidChange.getCall(2).args[0];
        await changeHandler();

        assert.isTrue(
            onConfigChangedCallback.calledOnce,
            'Expected onConfigChanged to be called when config file is changed',
        );
    });

    test('Server restarts when a config file is deleted', async () => {
        createConfigFileWatchers(onConfigChangedCallback);

        const deleteHandler = mockWatcher.onDidDelete.getCall(3).args[0];
        await deleteHandler();

        assert.isTrue(
            onConfigChangedCallback.calledOnce,
            'Expected onConfigChanged to be called when config file is deleted',
        );
    });

    test('Server restarts for each config file type on change', async () => {
        createConfigFileWatchers(onConfigChangedCallback);

        for (let i = 0; i < MYPY_CONFIG_FILES.length; i++) {
            const changeHandler = mockWatcher.onDidChange.getCall(i).args[0];
            await changeHandler();
        }

        assert.strictEqual(
            onConfigChangedCallback.callCount,
            MYPY_CONFIG_FILES.length,
            `Expected onConfigChanged to be called once for each of the ${MYPY_CONFIG_FILES.length} config file patterns`,
        );
    });

    test('Returns a disposable for each watcher', () => {
        const disposables = createConfigFileWatchers(onConfigChangedCallback);

        assert.strictEqual(disposables.length, MYPY_CONFIG_FILES.length);
        for (const d of disposables) {
            assert.isFunction(d.dispose);
        }
    });

    test('Should dispose all subscriptions and watcher on dispose', () => {
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        watchers[0].dispose();

        assert.strictEqual(changeDisposable.dispose.callCount, 1, 'Change subscription should be disposed');
        assert.strictEqual(createDisposable.dispose.callCount, 1, 'Create subscription should be disposed');
        assert.strictEqual(deleteDisposable.dispose.callCount, 1, 'Delete subscription should be disposed');
        assert.strictEqual(mockWatcher.dispose.callCount, 1, 'Watcher should be disposed');
    });

    test('Should not call callback after dispose', () => {
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        // Dispose the watcher
        watchers[0].dispose();

        // Get the handlers and call them after disposal
        const changeHandler = mockWatcher.onDidChange.getCall(0).args[0];
        changeHandler();

        assert.strictEqual(onConfigChangedCallback.callCount, 0, 'Callback should not be called after dispose');
    });
});
