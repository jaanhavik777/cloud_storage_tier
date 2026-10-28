import pytest
from cloud_storage_tier import process_storage_tenants, monitor_replication_latency


def tenant(tier="hot", buckets=None, active=True, vault=False):
    return {"account_active": active, "tier": tier,
            "has_backup_vault": vault, "buckets": buckets or []}


def test_single_active_hot_tenant():
    t = [tenant(buckets=[{"size_gb": 100, "corrupted": False, "egress_gb": 50}])]
    r = process_storage_tenants(t, 10.0)
    assert r["total_billed"] == 2.5
    assert r["status"] == "BILLED"


def test_invalid_tenants_type():
    with pytest.raises(ValueError):
        process_storage_tenants("not a list", 10.0)


def test_negative_support_fee():
    with pytest.raises(ValueError):
        process_storage_tenants([], -1)


def test_inactive_tenant_skipped():
    r = process_storage_tenants([tenant(active=False)], 10.0)
    assert r == {"total_billed": 0.0, "status": "ZERO_USAGE"}


def test_cool_tier_with_vault():
    t = [tenant("cool", [{"size_gb": 200}], vault=True)]
    r = process_storage_tenants(t, 5.0)
    assert r["total_billed"] == 8.0  # 200*0.015 + 5
    assert r["status"] == "BILLED"


def test_archive_large_bucket_discount_and_egress():
    t = [tenant("archive", [{"size_gb": 1000, "egress_gb": 150}])]
    r = process_storage_tenants(t, 0)
    assert r["total_billed"] == 8.5  # 1000*0.005*0.9 + 50*0.08
    assert r["status"] == "BILLED"


def test_unknown_tier_flagged():
    r = process_storage_tenants([tenant("platinum", [{"size_gb": 10}])], 0)
    assert r["status"] == "ZERO_USAGE"


def test_invalid_bucket_size():
    t = [tenant(buckets=[{"size_gb": 0}])]
    assert process_storage_tenants(t, 0)["status"] == "ZERO_USAGE"


def test_corrupted_bucket_non_archive():
    t = [tenant("hot", [{"size_gb": 100, "corrupted": True, "egress_gb": 200}])]
    r = process_storage_tenants(t, 0)
    assert r["total_billed"] == 8.0  # only egress: 100*0.08


def test_corrupted_bucket_archive_resets_charge():
    t = [tenant("archive", [{"size_gb": 100},
                            {"size_gb": 100, "corrupted": True},
                            {"size_gb": 100}], vault=True)]
    r = process_storage_tenants(t, 7.0)
    assert r["total_billed"] == 7.0  # charge reset, loop broken, vault fee only


def test_audit_flagged():
    t = [tenant("hot", [{"size_gb": -1}] * 5)]
    r = process_storage_tenants(t, 0)
    assert r["status"] == "AUDIT_FLAGGED"


def test_latency_no_data():
    assert monitor_replication_latency([]) == "NO_DATA"


def test_latency_alert():
    assert monitor_replication_latency([[100, 250, 300]]) == "SYNC_LAG_ALERT"


def test_latency_synced_with_streak_reset():
    assert monitor_replication_latency([[250, 100, 250, 100]]) == "SYNCED"


# ---- Extra tests for branch coverage ----

def test_no_tenants_at_all():
    assert process_storage_tenants([], 0) == {"total_billed": 0.0, "status": "ZERO_USAGE"}


def test_defaults_missing_keys():
    # tier defaults to "hot", buckets defaults to [], account_active defaults to False
    assert process_storage_tenants([{"account_active": True}], 0)["status"] == "ZERO_USAGE"
    assert process_storage_tenants([{"tier": "hot"}], 0)["status"] == "ZERO_USAGE"


def test_hot_large_bucket_with_egress_no_vault():
    t = [tenant("hot", [{"size_gb": 600, "egress_gb": 150}])]
    r = process_storage_tenants(t, 0)
    assert r["total_billed"] == pytest.approx(17.5)


def test_egress_exactly_100_not_charged():
    t = [tenant("hot", [{"size_gb": 100, "egress_gb": 100}])]
    assert process_storage_tenants(t, 0)["total_billed"] == 2.5


def test_bucket_exactly_500_no_discount():
    t = [tenant("hot", [{"size_gb": 500}])]
    assert process_storage_tenants(t, 0)["total_billed"] == 12.5


def test_exactly_four_flags_is_not_audit():
    t = [tenant("hot", [{"size_gb": 100}] + [{"size_gb": 0}] * 4)]
    assert process_storage_tenants(t, 0)["status"] == "BILLED"


def test_corrupted_archive_last_bucket_and_multi_tenant():
    t = [tenant("archive", [{"size_gb": 10, "corrupted": True}]),
         tenant("cool", [{"size_gb": 100}])]
    assert process_storage_tenants(t, 0)["total_billed"] == 1.5


def test_latency_second_node_alerts():
    assert monitor_replication_latency([[100, 100], [300, 300]]) == "SYNC_LAG_ALERT"


def test_latency_exactly_200_is_ok():
    assert monitor_replication_latency([[200, 200, 200]]) == "SYNCED"


def test_latency_empty_node_logs():
    assert monitor_replication_latency([[]]) == "SYNCED"
