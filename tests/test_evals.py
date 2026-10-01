from evals.checks import check_result

GOOD = {"currency": "INR", "results": [
    {"site": "a.in", "price": 100, "effective_price": 90, "url": "https://a.in/p"},
    {"site": "b.in", "price": 95, "effective_price": 95, "url": "https://b.in/p"}],
    "best_deal": {"site": "a.in", "effective_price": 90}}


def test_good_result_passes_and_ranges_work():
    assert check_result({"expected_min_price": 50, "expected_max_price": 120, "expected_stores_any": ["a.in"]}, GOOD) == []


def test_detects_common_failures():
    bad = {**GOOD, "results": GOOD["results"] + [{"site": "a.in", "price": 10, "effective_price": 20, "url": ""}],
           "best_deal": {"site": "b.in", "effective_price": 95}, "currency": ""}
    problems = " | ".join(check_result({"expected_min_price": 50}, bad))
    for word in ("duplicate", "above listed", "no product link", "not the lowest", "currency", "below expected"):
        assert word in problems
    assert check_result({}, {"results": []}) == ["no results"]
