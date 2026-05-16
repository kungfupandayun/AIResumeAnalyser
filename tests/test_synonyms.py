import pytest

from app.services.scorers.skills import load_synonyms, expand_with_synonyms


def test_load_synonyms_returns_dict():
    syns = load_synonyms()
    assert isinstance(syns, dict)
    assert "kubernetes" in syns
    assert "k8s" in syns["kubernetes"]


def test_load_synonyms_lowercases_keys_and_values():
    syns = load_synonyms()
    for canonical, aliases in syns.items():
        assert canonical == canonical.lower()
        for alias in aliases:
            assert alias == alias.lower()


def test_expand_with_synonyms_matches_alias_to_canonical():
    syns = {"kubernetes": ["k8s", "container orchestration"]}
    expanded = expand_with_synonyms("k8s", syns)
    assert "kubernetes" in expanded
    assert "k8s" in expanded


def test_expand_with_synonyms_matches_canonical_to_aliases():
    syns = {"kubernetes": ["k8s", "container orchestration"]}
    expanded = expand_with_synonyms("Kubernetes", syns)
    assert "kubernetes" in expanded
    assert "k8s" in expanded
    assert "container orchestration" in expanded


def test_expand_with_synonyms_unknown_term_returns_only_lowered_self():
    expanded = expand_with_synonyms("MadeUpThing", {})
    assert expanded == {"madeupthing"}
