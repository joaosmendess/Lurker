from typing import Any

from fastapi.testclient import TestClient


def profile_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "resume": "Full-stack dev, C# and React.",
        "work_modes": ["remote", "hybrid"],
        "accepted_cities": ["Maceió"],
        "seniority_levels": ["Junior", "pleno"],
        "contract_types": ["clt", "pj"],
        "salary_expectation": "CLT: R$ 5.000",
        "excluded_title_words": ["Estágio"],
    }
    body.update(overrides)
    return body


def test_get_without_profile_is_404(client: TestClient) -> None:
    assert client.get("/profile").status_code == 404


def test_put_creates_then_get_returns_it(client: TestClient) -> None:
    put = client.put("/profile", json=profile_body())

    assert put.status_code == 200
    body = client.get("/profile").json()
    assert body["resume"] == "Full-stack dev, C# and React."
    assert body["seniority_levels"] == ["junior", "pleno"]  # normalized, like the TOML import
    assert body["excluded_title_words"] == ["estágio"]
    assert "updated_at" in body


def test_put_replaces_the_whole_profile(client: TestClient) -> None:
    client.put("/profile", json=profile_body())

    client.put("/profile", json=profile_body(accepted_cities=["Recife"], work_modes=["onsite"]))

    body = client.get("/profile").json()
    assert body["accepted_cities"] == ["Recife"]
    assert body["work_modes"] == ["onsite"]


def test_preferred_stack_and_strict_mode_round_trip(client: TestClient) -> None:
    body = profile_body(preferred_stack=[".NET", "C#", ".NET"], strict_unknown_work_mode=True)

    saved = client.put("/profile", json=body).json()

    assert saved["preferred_stack"] == [".NET", "C#"]  # deduplicated, order kept
    assert saved["strict_unknown_work_mode"] is True


def test_unknown_stack_tag_is_rejected(client: TestClient) -> None:
    response = client.put("/profile", json=profile_body(preferred_stack=["Cobol++"]))

    assert response.status_code == 422
    assert "Cobol++" in response.text


def test_stack_options_lists_known_tags(client: TestClient) -> None:
    options = client.get("/profile/stack-options").json()

    assert options[:2] == ["C#", ".NET"]
    assert "React Native" in options


def test_put_validates_like_the_toml_import(client: TestClient) -> None:
    assert client.put("/profile", json=profile_body(work_modes=["remoto"])).status_code == 422
    assert client.put("/profile", json=profile_body(resume="  ")).status_code == 422
