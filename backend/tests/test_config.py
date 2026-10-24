from app.config import Settings


def test_default_cors_origin():
    assert Settings(_env_file=None).cors_origin_list == ["http://localhost:3000"]


def test_comma_separated_origins_from_env_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text("VERIFAI_CORS_ORIGINS=http://localhost:3000, https://app.example.com\n")
    assert Settings(_env_file=f).cors_origin_list == ["http://localhost:3000", "https://app.example.com"]


def test_json_list_is_still_accepted(monkeypatch):
    monkeypatch.setenv("VERIFAI_CORS_ORIGINS", '["https://a.example.com","https://b.example.com"]')
    assert Settings(_env_file=None).cors_origin_list == ["https://a.example.com", "https://b.example.com"]


def test_blank_entries_are_ignored(monkeypatch):
    monkeypatch.setenv("VERIFAI_CORS_ORIGINS", " ,https://a.example.com,, ")
    assert Settings(_env_file=None).cors_origin_list == ["https://a.example.com"]