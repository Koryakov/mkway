"""Shared read-only templates for the tests (card MW-085, decisions: R204, R207, R209). Not a test module.

A costly real build (an install in a scratch repository, say) runs ONCE per worker, in a folder of its own that tests never
write to: the template. A test that needs one gets a writable copy in its own `tmp_path` (`conftest.template_copy`). The
runtime guard refuses every write into a template folder, in every mode (`_hermetic.decide`), as on Windows a read-only flag
on a folder does not stop new files. The build runs with a scratch HOME, no `CLAUDECODE`, and git's search for a repository
stopped at the base temp folder. Standard library only (and `_hermetic`)."""
import contextlib
import os
import shutil
from pathlib import Path

import _hermetic

BUILD_ENV = ("HOME", "USERPROFILE", "GIT_CEILING_DIRECTORIES", "CLAUDECODE")
TEXT_LIMIT = 4_000_000  # a file above this size is not searched (no text file of a template is that big)


class TemplateHoldsItsPath(Exception):
    """A copy of this template would hold the template's own folder in a text file, so it would point back at the template
    (a git worktree's pointer files do): the test must keep building in its own `tmp_path`."""


def spellings(folder):
    """The ways a folder's absolute path appears in a text file: as the system writes it, with slashes, with doubled
    backslashes (in a JSON text), each for the resolved and the given form."""
    forms = set()
    for path in {Path(folder), Path(folder).resolve()}:
        forms.update({str(path), path.as_posix(), str(path).replace("\\", "\\\\")})
    return sorted(forms)


def files_holding(folder, template):
    """The text files below `folder` (posix paths relative to it) whose bytes name the folder `template`. A file with a zero
    byte in its first 8 KB is not text and is not searched; the object store of a repository is not searched either (its
    files are compressed and cannot hold a path as text)."""
    needles = [text.encode("utf-8") for text in spellings(template)]
    found = []
    for here, dirs, names in os.walk(folder):
        if Path(here).name == "objects" and Path(here).parent.name == "." + "gi" + "t":
            dirs[:] = []
            continue
        for name in names:
            path = Path(here) / name
            if path.stat().st_size > TEXT_LIMIT:
                continue
            data = path.read_bytes()
            if b"\0" in data[:8192]:  # not a text file (compiled bytecode names the build folder; it is rebuilt from source)
                continue
            if any(needle in data for needle in needles):
                found.append(path.relative_to(folder).as_posix())
    return sorted(found)


def copy_template(template, dest):
    """A writable copy of the folder `template` at `dest` (made if missing). `copyfile` copies the bytes and not the
    read-only flag, which `copy2` would carry over."""
    shutil.copytree(template, dest, copy_function=shutil.copyfile, dirs_exist_ok=True)
    return Path(dest)


@contextlib.contextmanager
def build_environment(home, base):
    """The process environment of a build: HOME and USERPROFILE name the folder `home`, git looks for a repository no
    higher than `base`, `CLAUDECODE` is absent. Yields what the build sees, and puts the old values back."""
    old = {name: os.environ.get(name) for name in BUILD_ENV}
    Path(home).mkdir(parents=True, exist_ok=True)
    os.environ.update(HOME=str(home), USERPROFILE=str(home), GIT_CEILING_DIRECTORIES=str(Path(base).resolve()))
    os.environ.pop("CLAUDECODE", None)
    try:
        yield {name: os.environ.get(name) for name in BUILD_ENV}
    finally:
        for name, value in old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class Templates:
    """The templates of one worker: `get(name, build)` builds `name` once (`build(folder)` fills an empty folder) and
    returns the folder. The same object is protected: `protected()` lists the folders the guard keeps tests out of."""

    def __init__(self, folder, base):
        self.folder, self.base = Path(folder).resolve(), Path(base).resolve()
        self._dirs, self._counts, self._env, self._holding, self._failed = {}, {}, {}, {}, {}
        self._extra = []

    def get(self, name, build):
        if name in self._failed:
            raise self._failed[name]
        if name not in self._dirs:
            folder = self.folder / f"t{len(self._dirs) + len(self._failed)}"
            try:
                with _hermetic.guard_exit(), build_environment(self.folder / "home", self.base) as seen:
                    folder.mkdir(parents=True)
                    self._env[name] = seen
                    build(folder)
                    self._holding[name] = files_holding(folder, folder)
            except BaseException as exc:
                self._failed[name] = exc
                raise
            self._counts[name] = 1
            self._dirs[name] = folder
        return self._dirs[name]

    def build_count(self, name):
        return self._counts.get(name, 0)

    def env_at_build(self, name):
        return dict(self._env[name])

    def holding(self, name):
        """The files of the built template `name` that name its own folder (empty: a copy is safe)."""
        return list(self._holding[name])

    def protect(self, folder):
        """Treat another folder (a shared source built once per run) as a template: tests never write to it."""
        self._extra.append(Path(folder).resolve())

    def protected(self):
        return [*self._dirs.values(), *self._extra]
