"""Unit tests for keyword labeling functions — crafted positives and negatives."""

from ml.weak_supervision.keyword_lfs import (
    ALL_KEYWORD_LFS,
    lf_bad_deploy,
    lf_capacity_exhaustion,
    lf_cascading_failure,
    lf_certificate_expiry,
    lf_config_change,
    lf_data_corruption,
    lf_database_failure,
    lf_dependency_failure,
    lf_dns,
    lf_human_error,
    lf_monitoring_gap,
    lf_network_partition,
    lf_quota_limit,
    lf_retry_storm,
    lf_thundering_herd,
)
from ml.weak_supervision.types import IncidentRecord, Vote


def _record(body: str, title: str = "", sections: dict[str, str] | None = None) -> IncidentRecord:
    return IncidentRecord(
        content_hash="abc123",
        title=title,
        summary=body[:200],
        body=body,
        sections=sections or {},
    )


class TestConfigChange:
    def test_positive_misconfiguration(self):
        r = _record("A misconfiguration change in the load balancer caused 502 errors.")
        assert lf_config_change(r).vote == Vote.POSITIVE

    def test_positive_feature_flag(self):
        r = _record("The feature flag was set to the wrong value, routing all traffic to beta.")
        assert lf_config_change(r).vote == Vote.POSITIVE

    def test_negative_code_deploy(self):
        r = _record("The new code deploy introduced a regression in the payment flow.")
        assert lf_config_change(r).vote == Vote.ABSTAIN


class TestRetryStorm:
    def test_positive_retry_storm(self):
        r = _record("A retry storm from the API gateway overwhelmed the auth service.")
        assert lf_retry_storm(r).vote == Vote.POSITIVE

    def test_positive_retry_amplification(self):
        r = _record(
            "Clients retried failed requests, the retry amplification overwhelmed the backend."
        )
        assert lf_retry_storm(r).vote == Vote.POSITIVE

    def test_negative_traffic_spike(self):
        r = _record("Traffic spiked 5x due to a viral marketing campaign.")
        assert lf_retry_storm(r).vote == Vote.ABSTAIN


class TestCascadingFailure:
    def test_positive_cascade(self):
        r = _record("The cascading failure took down three downstream services.")
        assert lf_cascading_failure(r).vote == Vote.POSITIVE

    def test_positive_propagation(self):
        r = _record("The failure propagated from the cache layer to the API layer.")
        assert lf_cascading_failure(r).vote == Vote.POSITIVE

    def test_negative_single_service(self):
        r = _record("The payment service experienced a timeout for 10 minutes.")
        assert lf_cascading_failure(r).vote == Vote.ABSTAIN


class TestDNS:
    def test_positive_dns_resolution(self):
        r = _record("DNS resolution failed, causing all API calls to timeout.")
        assert lf_dns(r).vote == Vote.POSITIVE

    def test_positive_cname(self):
        r = _record("The CNAME record was wrong, pointing to a decommissioned host.")
        assert lf_dns(r).vote == Vote.POSITIVE

    def test_negative_network(self):
        r = _record("The network link between the two data centers was severed.")
        assert lf_dns(r).vote == Vote.ABSTAIN


class TestCertificateExpiry:
    def test_positive_expired_cert(self):
        r = _record("The TLS certificate expired, causing all HTTPS connections to fail.")
        assert lf_certificate_expiry(r).vote == Vote.POSITIVE

    def test_positive_chain_error(self):
        r = _record("The certificate chain was invalid after the intermediate CA was rotated.")
        assert lf_certificate_expiry(r).vote == Vote.POSITIVE

    def test_negative_auth_failure(self):
        r = _record("The OAuth token expired and users could not log in.")
        assert lf_certificate_expiry(r).vote == Vote.ABSTAIN


class TestCapacityExhaustion:
    def test_positive_disk_full(self):
        r = _record("The disk was full, causing the database to stop accepting writes.")
        assert lf_capacity_exhaustion(r).vote == Vote.POSITIVE

    def test_positive_oom(self):
        r = _record("The container was killed due to OOM error after memory leak.")
        assert lf_capacity_exhaustion(r).vote == Vote.POSITIVE

    def test_negative_slow_response(self):
        r = _record("Response times increased by 200ms during peak hours.")
        assert lf_capacity_exhaustion(r).vote == Vote.ABSTAIN


class TestBadDeploy:
    def test_positive_deploy_bug(self):
        r = _record("The deploy contained a bug that caused null pointer exceptions.")
        assert lf_bad_deploy(r).vote == Vote.POSITIVE

    def test_positive_rollback(self):
        r = _record("Rolling back to the previous version resolved the issue.")
        assert lf_bad_deploy(r).vote == Vote.POSITIVE

    def test_negative_config(self):
        r = _record("The environment variable was set to the wrong value.")
        assert lf_bad_deploy(r).vote == Vote.ABSTAIN


class TestDependencyFailure:
    def test_positive_aws(self):
        r = _record("An AWS us-east-1 outage caused our S3 uploads to fail.")
        assert lf_dependency_failure(r).vote == Vote.POSITIVE

    def test_positive_third_party(self):
        r = _record("The third-party payment processor was unavailable for 30 minutes.")
        assert lf_dependency_failure(r).vote == Vote.POSITIVE

    def test_negative_internal(self):
        r = _record("Our user service crashed due to a memory leak.")
        assert lf_dependency_failure(r).vote == Vote.ABSTAIN


class TestNetworkPartition:
    def test_positive_split_brain(self):
        r = _record("A split brain occurred between the two database replicas.")
        assert lf_network_partition(r).vote == Vote.POSITIVE

    def test_positive_firewall(self):
        r = _record("A security group misconfiguration blocked all traffic to the VPC.")
        assert lf_network_partition(r).vote == Vote.POSITIVE

    def test_negative_app_timeout(self):
        r = _record("The application timed out after 30 seconds waiting for a response.")
        assert lf_network_partition(r).vote == Vote.ABSTAIN


class TestDatabaseFailure:
    def test_positive_deadlock(self):
        r = _record("A database deadlock caused all write operations to fail.")
        assert lf_database_failure(r).vote == Vote.POSITIVE

    def test_positive_replication_lag(self):
        r = _record("Database replication lag reached 60 seconds, causing stale reads.")
        assert lf_database_failure(r).vote == Vote.POSITIVE

    def test_negative_application_query(self):
        r = _record("The application was generating too many queries per request.")
        assert lf_database_failure(r).vote == Vote.ABSTAIN


class TestThunderingHerd:
    def test_positive_cache_stampede(self):
        r = _record("A cache stampede overwhelmed the backend after the Redis restart.")
        assert lf_thundering_herd(r).vote == Vote.POSITIVE

    def test_positive_thundering_herd(self):
        r = _record("The thundering herd problem occurred when all instances reconnected.")
        assert lf_thundering_herd(r).vote == Vote.POSITIVE

    def test_negative_gradual_traffic(self):
        r = _record("Traffic gradually increased over 2 hours during the sale event.")
        assert lf_thundering_herd(r).vote == Vote.ABSTAIN


class TestMonitoringGap:
    def test_positive_no_alerts(self):
        r = _record("No alerts were configured for the queue depth metric.")
        assert lf_monitoring_gap(r).vote == Vote.POSITIVE

    def test_positive_detected_late(self):
        r = _record("The issue was discovered 6 hours later when a customer reported it.")
        assert lf_monitoring_gap(r).vote == Vote.POSITIVE

    def test_negative_alert_fired(self):
        r = _record("The PagerDuty alert fired within 2 minutes of the error spike.")
        assert lf_monitoring_gap(r).vote == Vote.ABSTAIN


class TestHumanError:
    def test_positive_wrong_env(self):
        r = _record("An engineer accidentally deleted the production database table.")
        assert lf_human_error(r).vote == Vote.POSITIVE

    def test_positive_manual_action(self):
        r = _record("The operator ran the wrong command against the production cluster.")
        assert lf_human_error(r).vote == Vote.POSITIVE

    def test_negative_automated(self):
        r = _record("The CI pipeline deployed a broken artifact to production.")
        assert lf_human_error(r).vote == Vote.ABSTAIN


class TestDataCorruption:
    def test_positive_corruption(self):
        r = _record("Data corruption caused 50,000 user records to have null emails.")
        assert lf_data_corruption(r).vote == Vote.POSITIVE

    def test_positive_race_condition(self):
        r = _record("A race condition in the write path corrupted the order status field.")
        assert lf_data_corruption(r).vote == Vote.POSITIVE

    def test_negative_unavailable(self):
        r = _record("The database was unavailable for 2 hours but no data was lost.")
        assert lf_data_corruption(r).vote == Vote.ABSTAIN


class TestQuotaLimit:
    def test_positive_rate_limit(self):
        r = _record("We hit the API rate limit, blocking all requests with 429 errors.")
        assert lf_quota_limit(r).vote == Vote.POSITIVE

    def test_positive_instance_limit(self):
        r = _record("The EC2 instance limit prevented autoscaling from launching new nodes.")
        assert lf_quota_limit(r).vote == Vote.POSITIVE

    def test_negative_resource_exhaustion(self):
        r = _record("The Redis instance ran out of memory during peak load.")
        assert lf_quota_limit(r).vote == Vote.ABSTAIN


class TestSectionBoost:
    def test_root_cause_section_higher_confidence(self):
        r = _record(
            "The service was down.",
            sections={"root_cause": "A DNS resolution failure caused timeouts."},
        )
        result = lf_dns(r)
        assert result.vote == Vote.POSITIVE
        assert result.confidence == 0.9

    def test_body_only_lower_confidence(self):
        r = _record("A DNS resolution failure caused all API calls to timeout.")
        result = lf_dns(r)
        assert result.vote == Vote.POSITIVE
        assert result.confidence == 0.7


class TestAllLFsRegistered:
    def test_all_lfs_count(self):
        assert len(ALL_KEYWORD_LFS) == 15

    def test_all_labels_unique(self):
        labels = [lf.label for lf in ALL_KEYWORD_LFS]
        assert len(labels) == len(set(labels))

    def test_all_names_unique(self):
        names = [lf.name for lf in ALL_KEYWORD_LFS]
        assert len(names) == len(set(names))
