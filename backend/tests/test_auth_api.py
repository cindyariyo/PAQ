"""
Integration tests for /auth endpoints.
"""
from tests.conftest import make_user


class TestLogin:
    def test_new_study_code_creates_user(self, client):
        res = client.post("/auth/login", json={"study_code": "ABC123"})
        assert res.status_code == 200
        data = res.json()
        assert data["study_code"] == "ABC123"
        assert data["hexad_type"] == "Unknown"
        assert data["display_name"] is None
        assert "user_id" in data

    def test_existing_study_code_returns_same_user(self, client):
        res1 = client.post("/auth/login", json={"study_code": "ABC123"})
        res2 = client.post("/auth/login", json={"study_code": "ABC123"})
        assert res1.json()["user_id"] == res2.json()["user_id"]

    def test_study_code_trimmed(self, client):
        res = client.post("/auth/login", json={"study_code": "  ABC123  "})
        assert res.status_code == 200
        assert res.json()["study_code"] == "ABC123"

    def test_returning_user_with_display_name(self, client, db):
        user = make_user(db, study_code="XYZ999", display_name="Alice")
        res = client.post("/auth/login", json={"study_code": "XYZ999"})
        assert res.status_code == 200
        assert res.json()["display_name"] == "Alice"

    def test_returning_user_hexad_type_preserved(self, client, db):
        make_user(db, study_code="XYZ999", hexad_type="Player")
        res = client.post("/auth/login", json={"study_code": "XYZ999"})
        assert res.json()["hexad_type"] == "Player"


class TestSetDisplayName:
    def _login(self, client, code="USER01"):
        return client.post("/auth/login", json={"study_code": code}).json()["user_id"]

    def test_set_display_name_success(self, client):
        uid = self._login(client)
        res = client.post("/auth/set-display-name",
                          json={"user_id": uid, "display_name": "TestPlayer"})
        assert res.status_code == 200
        assert res.json()["display_name"] == "TestPlayer"
        assert res.json()["ok"] is True

    def test_display_name_trimmed(self, client):
        uid = self._login(client)
        res = client.post("/auth/set-display-name",
                          json={"user_id": uid, "display_name": "  Alice  "})
        assert res.json()["display_name"] == "Alice"

    def test_duplicate_display_name_rejected(self, client):
        uid1 = self._login(client, "USER01")
        uid2 = self._login(client, "USER02")
        client.post("/auth/set-display-name",
                    json={"user_id": uid1, "display_name": "SharedName"})
        res = client.post("/auth/set-display-name",
                          json={"user_id": uid2, "display_name": "SharedName"})
        assert res.status_code == 409

    def test_duplicate_name_case_insensitive(self, client):
        uid1 = self._login(client, "USER01")
        uid2 = self._login(client, "USER02")
        client.post("/auth/set-display-name",
                    json={"user_id": uid1, "display_name": "Alice"})
        res = client.post("/auth/set-display-name",
                          json={"user_id": uid2, "display_name": "alice"})
        assert res.status_code == 409

    def test_same_user_can_reset_own_name(self, client):
        uid = self._login(client)
        client.post("/auth/set-display-name",
                    json={"user_id": uid, "display_name": "OldName"})
        res = client.post("/auth/set-display-name",
                          json={"user_id": uid, "display_name": "NewName"})
        assert res.status_code == 200

    def test_empty_name_rejected(self, client):
        uid = self._login(client)
        res = client.post("/auth/set-display-name",
                          json={"user_id": uid, "display_name": "   "})
        assert res.status_code == 400

    def test_unknown_user_id_404(self, client):
        res = client.post("/auth/set-display-name",
                          json={"user_id": 9999, "display_name": "Ghost"})
        assert res.status_code == 404
