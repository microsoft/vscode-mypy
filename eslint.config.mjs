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
];
