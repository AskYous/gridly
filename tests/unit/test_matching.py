"""Finding a name by its letters, whichever matcher is doing the finding."""

import pytest

from gridly.matching import Search, letters_in, rank

#: Both ways the picker can match: Textual's, and the one here for when that
#: corner of Textual is not where it is today. Every promise the picker leans
#: on is checked against both.
BACKENDS = [True, False]

NAMES = [
    "overtime.gridly",
    "tasks.gridly",
    "users.gridly",
    "logins.gridly",
    "mystc4-ebu-screens.gridly",
]


def found(query, palette, names=NAMES):
    """The names a query finds, best fit first."""
    search = Search(query, palette=palette)
    scored = [(search.score(name), name) for name in names]
    return [name for score, name in sorted(scored, reverse=True) if score]


@pytest.mark.parametrize("palette", BACKENDS)
def test_the_letters_of_a_name_in_order_find_it(palette):
    assert found("ovt", palette) == ["overtime.gridly"]
    assert found("screens", palette) == ["mystc4-ebu-screens.gridly"]
    assert found("log", palette) == ["logins.gridly"]


@pytest.mark.parametrize("palette", BACKENDS)
def test_a_whole_name_finds_itself_first(palette):
    assert found("users", palette)[0] == "users.gridly"


@pytest.mark.parametrize("palette", BACKENDS)
def test_letters_out_of_order_find_nothing(palette):
    assert found("tvo", palette) == []


@pytest.mark.parametrize("palette", BACKENDS)
def test_a_name_that_is_not_there_finds_nothing(palette):
    assert found("zzz", palette) == []


@pytest.mark.parametrize("palette", BACKENDS)
def test_case_is_not_something_you_have_to_get_right(palette):
    assert found("OVT", palette) == found("ovt", palette) == ["overtime.gridly"]


@pytest.mark.parametrize("palette", BACKENDS)
def test_an_empty_query_finds_nothing_rather_than_everything(palette):
    """The picker shows the whole list itself in that case, unranked."""
    search = Search("", palette=palette)
    assert all(search.score(name) == 0 for name in NAMES)


@pytest.mark.parametrize("palette", BACKENDS)
def test_the_letters_it_found_are_the_ones_it_marks(palette):
    search = Search("ovt", palette=palette)
    marks = search.marks("overtime.gridly")
    print(palette, marks)
    assert "".join("overtime.gridly"[at] for at in marks) == "ovt"
    assert marks == sorted(marks), "and they are given in reading order"


@pytest.mark.parametrize("palette", BACKENDS)
def test_nothing_is_marked_on_a_name_the_query_does_not_find(palette):
    assert Search("zzz", palette=palette).marks("overtime.gridly") == []


@pytest.mark.parametrize("palette", BACKENDS)
def test_a_closer_fit_scores_higher(palette):
    """Which is what puts the sheet you meant at the top of the list."""
    search = Search("us", palette=palette)
    assert search.score("users.gridly") > search.score("mystc4-ebu-screens.gridly")


@pytest.mark.parametrize("palette", BACKENDS)
def test_holding_the_query_whole_beats_holding_it_in_pieces(palette):
    search = Search("ove", palette=palette)
    assert search.score("overtime") > search.score("o-v-e-r")
    assert search.score("overtime") > search.score("oxvxexr")


# --- the matcher here, on its own ------------------------------------------


def test_letters_in_gives_up_the_moment_one_is_missing():
    assert letters_in("ovt", "overtime") == [0, 1, 4]
    assert letters_in("ovz", "overtime") == []
    assert letters_in("", "overtime") == []


def test_a_letter_starting_a_word_counts_for_more_than_one_in_the_middle():
    assert rank("s", "sheets") > rank("s", "tasks")


def test_letters_that_follow_each_other_count_for_more_than_scattered_ones():
    assert rank("ove", "overtime") > rank("ove", "oxvxexr")


def test_nothing_scores_at_all_when_the_letters_are_not_all_there():
    assert rank("zzz", "overtime") == 0.0
