"""Unit tests for sparv.core.config."""
import copy

from sparv.core import config


def test_merge_dicts() -> None:
    """Test merging two dictionaries."""
    dict1 = {"a": 1, "b": 2, "d": 3, "f": {"g": 6}}
    dict2 = {"b": 3, "c": 4, "d": {"e": 5}, "f": {"g": 0, "h": 7}}
    dict2_original = copy.deepcopy(dict2)
    config._merge_dicts(dict1, dict2)
    assert dict1 == {"a": 1, "b": 2, "c": 4, "d": 3, "f": {"g": 6, "h": 7}}
    assert dict2 == dict2_original


def test_merge_dicts_replace() -> None:
    """Test merging two dictionaries with replacement."""
    dict1 = {"a": 1, "b": 2, "d": 3, "f": {"g": 6, "m": 8}}
    dict2 = {"b": 3, "c": 4, "d": {"e": 5}, "f": {"g": 0, "h": 7}}
    dict1_original = copy.deepcopy(dict1)
    dict2_original = copy.deepcopy(dict2)
    goal = {"a": 1, "b": 3, "c": 4, "d": {"e": 5}, "f": {"g": 0, "h": 7, "m": 8}}
    config._merge_dicts_replace(dict1, dict2)
    assert dict1 == goal
    assert dict2 == dict2_original

    # Test that we get the same result using _merge_dicts with the dictionaries swapped
    config._merge_dicts(dict2, dict1_original)
    assert dict2 == goal
