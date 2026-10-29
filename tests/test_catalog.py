def test_catalog_search_filters_and_archives(store):
    client, _ = store
    assert client.get("/").status_code == 200
    page = client.get("/catalog?q=тестовый")
    assert "Смеситель тестовый" in page.text
    assert "Архивный" not in page.text
    assert "Смеситель тестовый" not in client.get("/catalog?min_price=2000").text
    assert client.get("/products/1").status_code == 200
    assert client.get("/products/2").status_code == 404
    assert client.get("/catalog?min_price=abc").status_code == 422
