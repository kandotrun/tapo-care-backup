from tapo_care_backup.region import care_base_url, region_from_app_server_url


def test_region_from_app_server_url_extracts_known_prefixes():
    assert region_from_app_server_url("https://aps1-app-server.iot.i.tplinknbu.com") == "aps1"
    assert region_from_app_server_url("https://euw1-app-server.iot.i.tplinknbu.com") == "euw1"
    assert region_from_app_server_url("https://use1-app-cloudgateway.iot.i.tplinknbu.com") == "use1"


def test_region_from_app_server_url_defaults_to_aps1_for_missing_url():
    assert region_from_app_server_url(None) == "aps1"
    assert region_from_app_server_url("") == "aps1"


def test_care_base_url_builds_regional_tapo_care_host():
    assert care_base_url("aps1") == "https://aps1-app-tapo-care.i.tplinknbu.com"
