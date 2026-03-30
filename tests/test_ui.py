def test_ui_page_loads(client):
    response = client.get("/ui")

    assert response.status_code == 200
    assert "TraceCore Control Room" in response.text


def test_root_redirects_to_ui(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/ui"
