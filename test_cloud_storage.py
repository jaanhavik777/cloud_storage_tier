import pytest
from cloud_storage_tier import process_storage_tenants, monitor_replication_latency

# Example test case:
def test_single_active_hot_tenant():
    tenants = [
        {
            "account_active": True,
            "tier": "hot",
            "has_backup_vault": False,
            "buckets": [{"size_gb": 100, "corrupted": False, "egress_gb": 50}]
        }
    ]
    result = process_storage_tenants(tenants, 10.0)
    assert result["total_billed"] == 2.5
    assert result["status"] == "BILLED"

# TODO: Add test cases to achieve 90-100% on both Line and Branch coverage!