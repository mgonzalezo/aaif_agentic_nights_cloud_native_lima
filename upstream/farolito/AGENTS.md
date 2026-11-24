# AGENTS.md

## How to run the tests
- `python -m pytest -q` from the repository root. No network needed. Run it before you say you are done.

## Repo rules
- Keep changes to one file when possible.
- Error messages go to stderr and start with `farolito: `.
- A missing or unreadable config file must exit with code 2, never a traceback. The message is exactly
  `farolito: config file not found: <path>` on stderr (the tests check the words "config file not found").
- `main()` returns the process exit code as an int. Helper functions never call `sys.exit()`; they raise or return.
  Only the `if __name__ == "__main__":` guard turns the return value into an exit code with `sys.exit(main())`.
- Handle the error where `main()` can turn it into that return value, and keep the change small.
- Do not delete branches. Do not push to `main`; open a pull request.
