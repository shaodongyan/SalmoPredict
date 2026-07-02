# Releasing salmopredict

How to cut a new release to **PyPI** and **GitHub**. Run everything from a
**Python 3.10** environment (e.g. `conda activate salmopredict`), since the
package is pinned to Python 3.10 to match the model's pickle.

## Prerequisites (one-time)

- A PyPI account with maintainer access to the `salmopredict` project.
- A **project-scoped** API token from <https://pypi.org/manage/account/token/>
  (scope it to the `salmopredict` project, not the whole account). Store it in
  `~/.pypirc` so you never paste it on the command line or into chat:

  ```ini
  [pypi]
    username = __token__
    password = pypi-AgE...   # your token
  ```

- Build tooling in the env:

  ```bash
  pip install build twine
  ```

## Release steps

1. **Bump the version.** Edit `__version__ = "X.Y.Z"` in
   `salmopredict/__init__.py` — this is the single source of truth
   (`pyproject.toml` reads it via `[tool.setuptools.dynamic]`, and the CLI/GUI
   display it). PyPI never lets you re-upload an existing version, so this must
   increase every release (`0.1.2` → `0.1.3` for fixes, `0.2.0` for features).

2. **Commit and push the bump.**

   ```bash
   git add pyproject.toml
   git commit -m "Release X.Y.Z"
   git push origin main
   ```

3. **Build a clean sdist + wheel.**

   ```bash
   rm -rf dist build
   python -m build
   ```

4. **Sanity-check the artifacts.**

   ```bash
   twine check dist/*                                  # metadata + README render
   python -m zipfile -l dist/*.whl | grep -c "models/"  # expect 64 (model shipped)
   ```

   Both `dist/*.whl` and `dist/*.tar.gz` should be ~30 MB (they carry the bundled
   model). If the wheel is tiny, the model was not packaged — check
   `[tool.setuptools.package-data]` in `pyproject.toml` and `MANIFEST.in`.

5. **Test-install the built wheel** in a throwaway Python 3.10 env and run a
   prediction to confirm it works end to end:

   ```bash
   pip install dist/salmopredict-X.Y.Z-py3-none-any.whl
   salmopredict run -i examples/example_features.csv -o /tmp/sp_check
   ```

   (TestPyPI is skipped on purpose: AutoGluon's dependency tree is not on
   TestPyPI, so a TestPyPI install cannot resolve. This local wheel test is the
   reliable correctness check.)

6. **Upload to PyPI.**

   ```bash
   twine upload dist/*        # uses ~/.pypirc; otherwise it prompts
   ```

7. **Verify it is live.**

   ```bash
   curl -s https://pypi.org/pypi/salmopredict/X.Y.Z/json \
     | python -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"
   ```

   (The top-level `/pypi/salmopredict/json` "latest version" can lag a few
   minutes behind due to CDN caching; the version-specific URL above is
   authoritative.)

8. **Tag the release on GitHub.**

   ```bash
   git tag -a vX.Y.Z -m "salmopredict X.Y.Z"
   git push origin vX.Y.Z
   ```

## Notes

- **Python version is pinned on purpose.** The model is pickled with AutoGluon
  1.1.1 on Python 3.10, so `requires-python = ">=3.10,<3.11"`. Do not loosen it
  unless the model is re-trained/re-saved on a newer stack — otherwise installs
  will succeed on other Pythons but prediction will fail at load time.
- **The model ships inside the package** via two mechanisms, both required:
  `[tool.setuptools.package-data]` (`"salmopredict" = ["models/**"]`) puts it in
  the **wheel**, and `MANIFEST.in` puts it in the **sdist**.
- **The Streamlit GUI ships in the core dependencies.** `pip install
  salmopredict` gives both CLI and GUI. The `[gui]` extra is kept only as a
  no-op alias for backward compatibility.
- **Never expose a token.** Keep it in `~/.pypirc` or a CI secret, never in a
  command line, commit, PR, or chat. If a token is ever exposed, revoke it at
  <https://pypi.org/manage/account/token/> and mint a new one immediately.
