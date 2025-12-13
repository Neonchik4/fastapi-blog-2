import pytest


@pytest.mark.asyncio
async def test_pages_smoke(client, test_log):
    test_log("GET /")
    r = await client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")

    test_log("GET /auth/")
    r = await client.get("/auth/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
