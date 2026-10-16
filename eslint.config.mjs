import tseslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";

export default [
    {
        ignores: ["out", "dist", "**/*.d.ts"],
    },
    {
        files: ["src/**/*.ts"],
        languageOptions: {
            ecmaVersion: 6,
            sourceType: "module",
            parser: tsParser,
        },
        plugins: {
            "@typescript-eslint": tseslint,
        },
        rules: {
            "@typescript-eslint/naming-convention": "warn",
            curly: "warn",
            eqeqeq: "warn",
            "no-throw-literal": "warn",
            semi: "warn",
        },
    },
    {
        files: ['build/setup*.js', 'build/normalize-package-lock*.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'commonjs',
            globals: {
                __dirname: 'readonly',
                console: 'readonly',
                process: 'readonly',
            },
        },
        rules: {
            'no-unused-vars': 'error',
            'no-undef': 'error',
        },
    },
];
