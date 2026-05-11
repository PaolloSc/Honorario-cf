def test_download_invalid_uuid(client):
    """Path traversal attempt should be rejected."""
    response = client.get("/api/contract/../../etc/passwd/download")
    assert response.status_code in (400, 401, 422)


def test_download_nonexistent_contract(client):
    """Valid UUID but nonexistent contract should return 401 or 404."""
    response = client.get("/api/contract/00000000-0000-0000-0000-000000000000/download")
    assert response.status_code in (401, 404)
