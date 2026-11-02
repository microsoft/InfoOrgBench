# Contributing

This project welcomes contributions and suggestions. Most contributions
require you to agree to a Contributor License Agreement (CLA) declaring that
you have the right to, and actually do, grant us the rights to use your
contribution. For details, visit <https://cla.opensource.microsoft.com>.

When you submit a pull request, a CLA bot will automatically determine whether
you need to provide a CLA and decorate the PR appropriately (e.g., status
check, comment). Simply follow the instructions provided by the bot. You will
only need to do this once across all repos using our CLA.

This project has adopted the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

## Data contributions

Benchmark data has stricter rules than code:

- Do not add personal data, credentials or text without a licence that
  permits redistribution.
- Every new file must belong to a component in
  [release/manifest.json](release/manifest.json) that records its licence.
- Changing a task, reference or saved output changes its hash. Update
  `benchmark/manifest.json` and `benchmark/saved-results.json` together and
  confirm that `python -I -S -B benchmark/replay.py --receipt <file>` passes.
- Run `python tools/check_release.py` and
  `python -m unittest discover -s tests` before opening a pull request.

New sources or tasks change what the benchmark measures. Open an issue to
discuss them before submitting data.