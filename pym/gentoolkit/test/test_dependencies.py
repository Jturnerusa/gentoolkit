import portage
from typing import List, Dict, Optional
from pytest import MonkeyPatch
from gentoolkit.dependencies import Dependencies


def is_cp_in_cpv(cp: str, cpv: str) -> bool:
    other_cp, _, _ = portage.pkgsplit(cpv)
    return cp == other_cp


def environment(
    self: Dependencies,
    env_vars: List[str],
    fake_depends: Dict[str, Optional[Dict[str, str]]],
    fake_pkgs: List[str],
) -> List[str]:
    metadata = None
    for pkg in fake_pkgs:
        if is_cp_in_cpv(self.cp, pkg):
            if (metadata := fake_depends[pkg]) is not None:
                break
    else:
        return [""]
    results = list()
    for env_var in env_vars:
        try:
            value = metadata[env_var]
        except KeyError:
            value = ""
        results.append(value)
    return results


def test_basic_revdeps(monkeypatch: MonkeyPatch) -> None:
    fake_depends = {
        "app-misc/root-1.0": None,
        "app-misc/a-1.0": {"DEPEND": "app-misc/root"},
        "app-misc/b-1.0": {"DEPEND": "app-misc/a"},
        "app-misc/c-1.0": {"DEPEND": "app-misc/b"},
        "app-misc/d-1.0": None,
    }
    fake_pkgs = list(fake_depends.keys())

    def e(self, env_vars):
        return environment(self, env_vars, fake_depends, fake_pkgs)

    monkeypatch.setattr(Dependencies, "environment", e)

    # confirm that monkeypatch is working as expected
    assert Dependencies("app-misc/root").environment(["DEPEND"]) == [""]
    assert Dependencies("app-misc/a").environment(["DEPEND"]) == ["app-misc/root"]
    assert Dependencies("app-misc/b").environment(["DEPEND"]) == ["app-misc/a"]
    assert Dependencies("app-misc/c").environment(["DEPEND"]) == ["app-misc/b"]
    assert Dependencies("app-misc/d").environment(["DEPEND"]) == [""]

    assert sorted(
        pkg.cpv
        for pkg in Dependencies("app-misc/root").graph_reverse_depends(pkgset=fake_pkgs)
    ) == ["app-misc/a-1.0"]

    assert sorted(
        pkg.cpv
        for pkg in Dependencies("app-misc/root").graph_reverse_depends(
            pkgset=fake_pkgs, only_direct=False
        )
    ) == [
        "app-misc/a-1.0",
        "app-misc/b-1.0",
        "app-misc/c-1.0",
    ]


def test_evaluated_flags(monkeypatch: MonkeyPatch) -> None:
    fake_depends = {
        "app-misc/root-1.0": None,
        "app-misc/e-1.0": {"DEPEND": "app-misc/root"},
        "app-misc/f-1.0": {"DEPEND": "foo? ( app-misc/e )"},
        "app-misc/g-1.0": {"DEPEND": "bar? ( app-misc/f )"},
        "app-misc/h-1.0": {"DEPEND": "foo? ( bar? ( app-misc/e ) )"},
        "app-misc/i-1.0": {"DEPEND": "never? ( app-misc/root )"},
    }
    fake_pkgs = list(fake_depends.keys())
    # we will mutate the list to change the monkey patched use flags
    use: List[str] = []

    def e(self, env_vars):
        return environment(self, env_vars, fake_depends, fake_pkgs)

    def g(self):
        return use

    monkeypatch.setattr(Dependencies, "environment", e)
    monkeypatch.setattr(Dependencies, "_get_active_use", g)

    assert sorted(
        pkg.cpv
        for pkg in Dependencies("app-misc/root").graph_reverse_depends(
            pkgset=fake_pkgs, only_direct=False, evaluate_use=True
        )
    ) == [
        "app-misc/e-1.0",
    ]

    use = ["foo"]
    assert sorted(
        pkg.cpv
        for pkg in Dependencies("app-misc/root").graph_reverse_depends(
            pkgset=fake_pkgs, only_direct=False, evaluate_use=True
        )
    ) == ["app-misc/e-1.0", "app-misc/f-1.0"]

    # this test looks like it's incorrect, but the algorithm for evaluating use flags only
    # takes into account the conditional that is directly adjacent to the dep in the DEPEND
    # expression.
    use = ["bar"]
    assert sorted(
        pkg.cpv
        for pkg in Dependencies("app-misc/root").graph_reverse_depends(
            pkgset=fake_pkgs, only_direct=False, evaluate_use=True
        )
    ) == ["app-misc/e-1.0", "app-misc/h-1.0"]

    use = ["foo", "bar"]
    assert sorted(
        pkg.cpv
        for pkg in Dependencies("app-misc/root").graph_reverse_depends(
            pkgset=fake_pkgs, only_direct=False, evaluate_use=True
        )
    ) == ["app-misc/e-1.0", "app-misc/f-1.0", "app-misc/g-1.0", "app-misc/h-1.0"]
