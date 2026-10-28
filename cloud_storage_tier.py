def process_storage_tenants(tenants, fixed_support_fee):
    if not isinstance(tenants, list) or fixed_support_fee < 0:
        raise ValueError("Invalid tenants list or support fee")

    total_billed = 0.0
    flagged_buckets = 0

    for tenant in tenants:
        if not tenant.get("account_active", False):
            continue

        tier = tenant.get("tier", "hot")
        buckets = tenant.get("buckets", [])

        if tier == "hot":
            rate_per_gb = 0.025
        elif tier == "cool":
            rate_per_gb = 0.015
        elif tier == "archive":
            rate_per_gb = 0.005
        else:
            flagged_buckets += 1
            continue

        tenant_charge = 0.0

        for bucket in buckets:
            size_gb = bucket.get("size_gb", 0)
            is_corrupted = bucket.get("corrupted", False)
            egress_gb = bucket.get("egress_gb", 0)

            if size_gb <= 0:
                flagged_buckets += 1
                continue

            if is_corrupted:
                flagged_buckets += 1
                if tier == "archive":
                    tenant_charge = 0.0
                    break
                tenant_charge += 0.0
            elif size_gb > 500:
                tenant_charge += (size_gb * rate_per_gb) * 0.90
            else:
                tenant_charge += size_gb * rate_per_gb

            if egress_gb > 100:
                tenant_charge += (egress_gb - 100) * 0.08

        if tenant.get("has_backup_vault", False):
            tenant_charge += fixed_support_fee

        total_billed += tenant_charge

    if flagged_buckets > 4:
        return {"total_billed": round(total_billed, 2), "status": "AUDIT_FLAGGED"}
    if total_billed == 0.0:
        return {"total_billed": 0.0, "status": "ZERO_USAGE"}
    return {"total_billed": round(total_billed, 2), "status": "BILLED"}


def monitor_replication_latency(cluster_matrix):
    if not cluster_matrix:
        return "NO_DATA"

    for node_logs in cluster_matrix:
        lag_streak = 0
        for latency_ms in node_logs:
            if latency_ms > 200:
                lag_streak += 1
                if lag_streak >= 2:
                    return "SYNC_LAG_ALERT"
            else:
                lag_streak = 0
    return "SYNCED"