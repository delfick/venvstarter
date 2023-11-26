def ensure_packaging_module(packaging_version):
    import importlib
    import os
    import sys

    try:
        __import__("packaging")
    except ImportError:
        os.system(f"{sys.executable} -m pip install packaging")

    import packaging
    from packaging.specifiers import SpecifierSet

    if not any(str(packaging_version).startswith(ch) for ch in ("=", ">", "<")):
        packaging_version = f"=={packaging_version}"

    specifier = SpecifierSet(packaging_version)

    if packaging.__version__ not in specifier:
        os.system(f"{sys.executable} -m pip install 'packaging{specifier}'")
        importlib.reload(packaging)
        return __import__("packaging")
    else:
        return packaging


def determine_if_needs_installation(deps, no_binary, packaging_version):
    import importlib
    import sys

    def with_pkg_resources():
        import pkg_resources  # type: ignore[import]

        try:
            pkg_resources.working_set.require(deps)
        except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as error:
            sys.stderr.write(str(error) + "\\n\\n")
            sys.stderr.flush()
            raise SystemExit(1)

    def with_importlib_metadata():
        import sys
        from collections import defaultdict
        from importlib.metadata import PackageNotFoundError, requires, version

        ensure_packaging_module(packaging_version)
        from packaging.requirements import Requirement

        need = defaultdict(list)
        have = {}
        checked = set()
        deps_list = list(deps)

        while deps_list:
            dep = deps_list.pop(0)
            if dep in checked:
                continue

            checked.add(dep)
            req = Requirement(dep)

            if req.marker and not req.marker.evaluate():
                continue

            need[req.name].append(req.specifier)

            if req.name not in have:
                req_name = req.name
                if req.name.startswith("backports-"):
                    try:
                        version(req.name)
                    except PackageNotFoundError:
                        req_name = req_name.replace("-", ".", 1)

                try:
                    have[req.name] = version(req_name)
                except PackageNotFoundError as error:
                    sys.stderr.write(f"{error}\n\n")
                    sys.stderr.flush()
                    raise SystemExit(1)

            for tag in ("", *req.extras):
                for dist_dep in requires(req_name) or []:
                    dist_req = Requirement(dist_dep)
                    if dist_req.marker and not dist_req.marker.evaluate({"tag": tag}):
                        continue

                    dist_req.extras = set()
                    dist_dep = str(dist_req)
                    deps_list.append(dist_dep)

        for name, specifiers in need.items():
            installed = have[name]
            for specifier in specifiers:
                if installed not in specifier:
                    sys.stderr.write(
                        f"Package {name} needs {specifier} but is installed as {installed}\n\n"
                    )
                    sys.stderr.flush()
                    raise SystemExit(1)

    if sys.version_info < (3, 8):
        with_pkg_resources()
    else:
        with_importlib_metadata()

    for name in no_binary:
        if importlib.import_module(name).__file__.endswith(".so"):
            sys.stderr.write(f"{name} needs to not be a binary installation\\n\\n")
            sys.stderr.flush()
            raise SystemExit(1)
