import base64
import hashlib
import hmac

from tapo_care_backup.signing import content_md5, x_authorization


def test_content_md5_matches_tapo_header_format():
    assert content_md5("{}") == base64.b64encode(hashlib.md5(b"{}").digest()).decode()


def test_x_authorization_is_deterministic_for_supplied_nonce_and_timestamp():
    content = "{}"
    endpoint = "/api/v2/account/login"
    timestamp = "1700000000"
    nonce = "00000000-0000-0000-0000-000000000000"
    access_key = "test-access-key"
    secret = "test-secret"

    payload = "\n".join([content_md5(content), timestamp, nonce, endpoint]).encode()
    expected_sig = hmac.new(secret.encode(), payload, hashlib.sha1).digest().hex()

    assert x_authorization(content, endpoint, timestamp, nonce, access_key, secret) == (
        f"Timestamp={timestamp}, Nonce={nonce}, AccessKey={access_key}, Signature={expected_sig}"
    )
