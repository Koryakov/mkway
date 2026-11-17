"""MW-079: tests/shell is a package, so its test files may share a name with a file of a flat test folder."""


def test_a_shell_test_module_belongs_to_the_shell_package():
    """Catches: tests/shell without __init__.py, where a test module is imported under its bare file name."""
    assert __name__ == "shell.test_mw079_package"
