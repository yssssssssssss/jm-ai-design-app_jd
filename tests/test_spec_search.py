import re

from app.spec_search import search_specs


def _csrf(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def _register(client, username: str = "alice"):
    page = client.get("/register")
    response = client.post(
        "/register",
        data={
            "username": username,
            "password": "secret123",
            "invite_code": "invite-123",
            "csrf_token": _csrf(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_search_specs_returns_bottom_nav_text_and_assets():
    payload = search_specs("底部导航栏 坑位")

    assert payload["results"]
    assert any(result["spec_id"] == "bottom-nav" for result in payload["results"])
    bottom_nav = next(result for result in payload["results"] if result["spec_id"] == "bottom-nav")
    assert "底部导航栏" in bottom_nav["spec_label"]
    assert "坑位" in bottom_nav["excerpt"]
    assert bottom_nav["assets"]
    assert bottom_nav["assets"][0]["url"].startswith("/spec-snippets/bottom-nav/")


def test_search_specs_can_match_b_design_and_jm_ai():
    b_design = search_specs("任务规划 组件状态")
    jm_ai = search_specs("AI 按钮 颜色")

    assert any(result["spec_id"] == "b-design" for result in b_design["results"])
    assert any(result["spec_id"] == "jm-ai" for result in jm_ai["results"])


def test_search_specs_returns_two_results_by_default():
    payload = search_specs("规范")

    assert len(payload["results"]) <= 2


def test_search_specs_rejects_empty_query():
    try:
        search_specs("   ")
    except ValueError as exc:
        assert str(exc) == "empty query"
    else:
        raise AssertionError("empty query should fail")


def test_spec_search_page_requires_login(client):
    response = client.get("/spec-search", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_spec_search_page_renders_chat_ui_and_navigation(client):
    _register(client)
    response = client.get("/spec-search")

    assert response.status_code == 200
    assert "规范搜索" in response.text
    assert "规范审核" in response.text
    assert "spec-search-input" in response.text
    assert "spec-back-to-top" in response.text
    assert 'data-spec-search' in response.text
    assert 'href="/spec-search"' in response.text


def test_spec_search_query_returns_json_results(client):
    _register(client)
    response = client.post("/spec-search/query", data={"query": "底部导航栏"})

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]
    assert len(data["results"]) <= 2
    assert any(result["spec_id"] == "bottom-nav" for result in data["results"])


def test_spec_search_query_rejects_empty_query(client):
    _register(client)
    response = client.post("/spec-search/query", data={"query": "  "})

    assert response.status_code == 400
    assert response.json()["error"] == "请输入要检索的规范问题"
