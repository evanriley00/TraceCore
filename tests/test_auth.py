def test_register_and_login_flow(client):
    register_response = client.post(
        "/auth/register",
        json={
            "email": "engineer@example.com",
            "password": "super-secret-password",
            "full_name": "Trace Engineer",
        },
    )
    assert register_response.status_code == 201
    registered = register_response.json()
    assert registered["access_token"]
    assert registered["api_key"].startswith("tc_")
    assert registered["user"]["email"] == "engineer@example.com"

    login_response = client.post(
        "/auth/login",
        json={
            "email": "engineer@example.com",
            "password": "super-secret-password",
        },
    )
    assert login_response.status_code == 200
    logged_in = login_response.json()
    assert logged_in["access_token"]
    assert logged_in["user"]["email"] == "engineer@example.com"

