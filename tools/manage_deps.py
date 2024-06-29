from venvstarter import dependencies


class Deps(dependencies.Deps):
    def set_requirements(self) -> None:
        self.add_local_dep(
            path=self.project_root,
            version_file=self.project_root / "venvstarter" / "version.py",
            name="venvstarter=={version}",
            tags=["tests", "dev"],
        )

        in_tox = self.respect_tox()

        if not in_tox:
            self.add_requirements_file(
                self.project_root / "tools" / "requirements.local.txt", missing_ok=True
            )
            self.add_requirements_file(
                self.project_root / "tools" / "requirements.docs.txt"
            )


if __name__ == "__main__":
    Deps.from_cli().apply()
