from cryptography.fernet import Fernet

from apps.api.auth.token_store import EncryptedTokenStore, OAuthToken


def test_oauth_tokens_are_encrypted_and_tenant_scoped() -> None:
    records = {}
    store = EncryptedTokenStore(Fernet.generate_key(), records)
    store.put("tenant-a", "upwork", OAuthToken("access-secret", "refresh-secret"))

    record = records[("tenant-a", "upwork")]
    assert b"access-secret" not in record.access_token_ciphertext
    assert store.get("tenant-b", "upwork") is None
    assert store.get("tenant-a", "upwork") == OAuthToken("access-secret", "refresh-secret")
    assert store.list_connections("tenant-a") == ["upwork"]
    assert store.delete("tenant-a", "upwork") is True
