def determine_if_needs_installation(
    uv: str, deps: list[str], no_binary: list[str]
) -> None:
    import importlib
    import sys
    from collections import defaultdict
    from importlib.metadata import PackageNotFoundError, requires, version

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
                if dist_req.marker and not dist_req.marker.evaluate({"extra": tag}):
                    continue

                dist_req.extras = set()
                dist_dep = str(dist_req)
                deps_list.append(dist_dep.split(";", 1)[0])

    for name, specifiers in need.items():
        installed = have[name]
        for specifier in specifiers:
            if installed not in specifier:
                sys.stderr.write(
                    f"Package {name} needs {specifier} but is installed as {installed}\n\n"
                )
                sys.stderr.flush()
                raise SystemExit(1)

    for name in no_binary:
        mod = importlib.import_module(name)
        if mod and mod.__file__ and mod.__file__.endswith(".so"):
            sys.stderr.write(f"{name} needs to not be a binary installation\\n\\n")
            sys.stderr.flush()
            raise SystemExit(1)
