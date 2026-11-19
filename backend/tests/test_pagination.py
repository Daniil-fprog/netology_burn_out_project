from app.utils.pagination import paginate


def test_paginate_returns_requested_slice_and_total():
    assert paginate([1, 2, 3, 4, 5], page=2, page_size=2) == {
        "page": 2,
        "page_size": 2,
        "total": 5,
        "items": [3, 4],
    }
