import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from tapo_care_backup.crypto import decrypt_tapo_payload


def test_decrypt_tapo_payload_returns_plain_content_without_key():
    assert decrypt_tapo_payload(b"plain-video", None) == b"plain-video"


def test_decrypt_tapo_payload_uses_first_16_bytes_as_iv_for_aes_cbc():
    key = b"0123456789abcdef"
    iv = b"abcdef0123456789"
    plaintext = b"hello tapo video"
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_payload = iv + cipher.encrypt(pad(plaintext, AES.block_size))

    assert decrypt_tapo_payload(encrypted_payload, base64.b64encode(key).decode()) == plaintext
