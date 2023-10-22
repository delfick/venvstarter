class ScriptNotFound(Exception):
    def __init__(self, location, name):
        super().__init__()
        self.name = name
        self.location = location

    def __str__(self):
        available = ", ".join(
            n.name for n in self.location.parent.iterdir() if "." not in n.name and n.exists()
        )
        return "\n".join(
            [
                "\nCouldn't find the executable!",
                f"Wanted {self.name}",
                f"Available is {available}",
            ]
        )


class FailedToGetOutput(Exception):
    def __init__(self, error, stderr):
        super().__init__()
        self.error = error
        self.stderr = stderr

    def __str__(self):
        return f"Failed to get output\nstderr: {self.stderr}\nerror: {self.error}"


class VersionNotSpecified(Exception):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def __str__(self):
        return f"A version_file was specified for a local dependency, but '{{version}}' not found in the name: {self.name}"


class InvalidVersion(Exception):
    def __init__(self, want):
        super().__init__()
        self.want = want

    def __str__(self):
        return f"Version needs to be an int, float or string, got {self.want}"
