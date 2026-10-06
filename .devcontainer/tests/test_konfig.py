import dataclasses
from pathlib import Path

import pytest

from devcontainer.konfig import Konfig, Sammlung, claude_json, lade_konfig, netz_env, skills_liste

BEISPIEL_TOML = """
[github_app]
slug = "beispiel-app"
app_id = 1
installation_id = 2
bot_user_id = 42

[broker]
repository = "Repo"
port = 8790

[broker.rollen.bau]
contents = "write"

[devcontainer]
repository = "Beispiel/Repo"

[[devcontainer.skills]]
plugin = "beispiel-skills"
github = "beispiel/skills"
version = "v1.2.3"
commit = "0123456789abcdef0123456789abcdef01234567"

[netz]
github_meta = ["web", "api", "git"]
domains = ["api.example.org", "pakete.example.org"]
"""

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def konfig(tmp_path: Path) -> Konfig:
    pfad = tmp_path / "harness.toml"
    pfad.write_text(BEISPIEL_TOML, encoding="utf-8")
    return lade_konfig(pfad)


def test_bot_identitaet_aus_der_app(konfig: Konfig) -> None:
    assert konfig.bot_name == "beispiel-app[bot]"
    assert konfig.bot_email == "42+beispiel-app[bot]@users.noreply.github.com"


def test_image_und_repo_name_aus_dem_repository(konfig: Konfig) -> None:
    assert konfig.repository == "Beispiel/Repo"
    assert konfig.image == "ghcr.io/beispiel/repo/devcontainer"
    assert konfig.repo_name == "Repo"


def test_broker_port_und_rollen(konfig: Konfig) -> None:
    assert konfig.broker_port == 8790
    assert konfig.rollen == ("bau",)


def test_netz_env_hat_genau_drei_zeilen(konfig: Konfig) -> None:
    assert netz_env(konfig).splitlines() == [
        "BROKER_PORT=8790",
        'GITHUB_META="web api git"',
        'DOMAINS="api.example.org pakete.example.org"',
    ]


@pytest.mark.parametrize("domain", ["a b.example.org", 'a".example.org', "$(id).example.org", ""])
def test_netz_env_lehnt_unsichere_domains_ab(konfig: Konfig, domain: str) -> None:
    kaputt = dataclasses.replace(konfig, domains=(domain,))
    with pytest.raises(ValueError, match="Domain"):
        netz_env(kaputt)


def test_echte_harness_toml_laesst_sich_laden() -> None:
    konfig = lade_konfig(REPO_ROOT / "harness.toml")
    assert konfig.domains
    assert konfig.github_meta
    assert konfig.image.startswith("ghcr.io/")
    skills_liste(konfig)  # wirft bei unsicheren Werten


def test_skill_sammlungen_mit_fester_version(konfig: Konfig) -> None:
    assert konfig.skills == (
        Sammlung(
            plugin="beispiel-skills",
            github="beispiel/skills",
            version="v1.2.3",
            commit="0123456789abcdef0123456789abcdef01234567",
        ),
    )


def test_skills_liste_eine_zeile_je_sammlung(konfig: Konfig) -> None:
    assert skills_liste(konfig).splitlines() == [
        "beispiel-skills beispiel/skills v1.2.3 0123456789abcdef0123456789abcdef01234567"
    ]


@pytest.mark.parametrize(
    ("feld", "wert"),
    [
        ("plugin", "a b"),
        ("plugin", "$(id)"),
        ("github", "nur-ein-teil"),
        ("github", "a/b/c"),
        ("github", "a/b;id"),
        ("version", "-v1"),
        ("version", "refs/tags/v1"),
        ("version", ""),
        ("commit", "6acc160"),
        ("commit", "Z" * 40),
    ],
)
def test_skills_liste_lehnt_unsichere_werte_ab(konfig: Konfig, feld: str, wert: str) -> None:
    kaputt = dataclasses.replace(konfig, skills=(dataclasses.replace(konfig.skills[0], **{feld: wert}),))
    with pytest.raises(ValueError, match=feld):
        skills_liste(kaputt)


def test_claude_vertraut_dem_clone_ohne_rueckfrage(konfig: Konfig) -> None:
    basis = {"hasCompletedOnboarding": True}
    assert claude_json(konfig, basis) == {
        "hasCompletedOnboarding": True,
        "projects": {"/arbeit/Repo": {"hasTrustDialogAccepted": True}},
    }
