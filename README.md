# Sparv – Språkbanken's Analysis Platform

Sparv is a text analysis tool run from the command line. The documentation can be found here:
https://spraakbanken.gu.se/sparv.

Check the [changelog](CHANGELOG.md) to see what's new!

Sparv is developed by [Språkbanken](https://spraakbanken.gu.se/). The source code is available under the [MIT
license](https://opensource.org/licenses/MIT).

If you have any questions, problems or suggestions please contact <sb-sparv@svenska.gu.se>.

## Prerequisites

* A Unix-like environment (e.g. Linux, OS X or [Windows Subsystem for
  Linux](https://docs.microsoft.com/en-us/windows/wsl/about)) *Note:* Most of Sparv's features should work in a Windows
  environment as well, but since we don't do any testing on Windows we cannot guarantee anything.
* [Python 3.11](https://python.org/) or newer.

## Installation

Sparv is available on [PyPI](https://pypi.org/project/sparv/) and can be installed using
[pip](https://pip.pypa.io/en/stable/installation/) or [pipx](https://pipx.pypa.io/stable/).
We recommend using pipx, which will install Sparv in an isolated environment while still making it available to be run
from anywhere.

```sh
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install sparv
```

Now you should be ready to run the Sparv command! Try it by typing `sparv --help`.

Sparv can be used together with several plugins and third-party software. Please check the [Sparv user
manual](https://spraakbanken.gu.se/sparv/user-manual/installation-and-setup/) for more details!

## Running tests

If you want to run the tests you will need to clone this project from
[GitHub](https://github.com/spraakbanken/sparv) since the test data is not distributed with pip.

Before cloning the repository with [git](https://git-scm.com/downloads) make sure you have [Git Large File
Storage](https://git-lfs.github.com/) installed (`apt install git-lfs`). Some files will not be downloaded correctly
otherwise. If you happen to clone the repository before installing Git Large File Storage you will have to run `git lfs
fetch` in order to update the corpus and annotation files.

Install the dependencies, including the dev dependencies. We recommend that you first set up a virtual environment:

```sh
python3 -m venv venv
source venv/bin/activate
pip install -e .[dev]
```

Now with the virtual environment activated you can run `pytest` from the `sparv` directory. You can run
particular tests using the provided markers (e.g. `pytest -m swe` to run the Swedish tests only) or via substring
matching (e.g. `pytest -k "not slow"` to skip the slow tests).
