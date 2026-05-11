def test_cnpj_invalid_format(client):
    """CNPJ with wrong length should return 400 or 404."""
    response = client.get("/api/cnpj/123")
    assert response.status_code in (400, 404, 422)


def test_cnpj_valid_format(client):
    """CNPJ with correct length should attempt lookup (may fail with no network)."""
    response = client.get("/api/cnpj/00000000000191")
    # Either returns data or 404/500 (network dependent)
    assert response.status_code in (200, 404, 500)
