# Hindsight Incident Taxonomy v1

**Version:** 1.0
**Date:** 2026-07-16
**Status:** Active

---

## Purpose

This taxonomy provides a controlled vocabulary for classifying incident
post-mortems by root cause and failure mode. Labels are **multi-label**: a single
incident may have multiple root causes (e.g., a bad deploy that triggers a
cascading failure).

Labels are designed to be:

- **Mutually orthogonal** — each label captures a distinct failure mode.
- **Empirically grounded** — every label must have ≥ 30 silver positives in the
  corpus or it is merged/dropped.
- **Annotator-friendly** — definitions are concrete; inclusion/exclusion criteria
  resolve ambiguity.

---

## Label Inventory (15 labels)

### 1. `config-change`

**Definition:** Incident caused by a configuration change (feature flag, environment variable, infrastructure-as-code parameter, DNS record, load balancer rule) that introduced incorrect or incompatible behavior.

**Inclusion criteria:**
- A specific configuration change is identified as the root cause.
- Includes misconfigurations, typos in config, wrong environment promoted.

**Exclusion criteria:**
- Code deployments → `bad-deploy`.
- Infrastructure scaling parameters → `capacity-exhaustion` (unless the scaling config itself was wrong).

**Positive examples:**
1. "A misconfigured feature flag caused all users to be routed to the beta endpoint."
2. "The DNS TTL was changed from 300 to 0, causing upstream resolvers to query on every request."

**Near-miss:** "A new microservice was deployed with incorrect environment variables" → `bad-deploy` (the config was part of the deploy artifact).

---

### 2. `retry-storm`

**Definition:** A retry amplification loop where failed requests trigger retries that overwhelm the target service, creating a positive feedback cycle.

**Inclusion criteria:**
- Explicit mention of retry amplification, retry storms, or exponential retry blowup.
- Clients retrying failed requests causing cascading load.

**Exclusion criteria:**
- Sudden organic traffic spike with no retry component → `thundering-herd` or `capacity-exhaustion`.
- Cascading failures without retry amplification → `cascading-failure`.

**Positive examples:**
1. "When the payment service returned 503, all clients retried simultaneously with no backoff, amplifying traffic 10x."
2. "The retry storm from the API gateway overwhelmed the auth service."

**Near-miss:** "Traffic spiked 5x due to a viral post" → `capacity-exhaustion` (organic, not retry-driven).

---

### 3. `cascading-failure`

**Definition:** A failure in one component propagates to dependent components, causing a widening chain of failures across the system.

**Inclusion criteria:**
- Failure in service A causes service B, C, etc. to fail.
- Thread/connection pool exhaustion propagating upstream.
- Circuit breakers not in place or not triggered.

**Exclusion criteria:**
- Single-service failure with no propagation.
- Retry-driven amplification → `retry-storm` (though both may co-occur).

**Positive examples:**
1. "The database connection pool was exhausted, causing the API to queue requests, which timed out the load balancer, which returned 502 to all clients."
2. "When the recommendation service went down, the product page service blocked on synchronous calls, taking down checkout."

**Near-miss:** "The cache layer failed and all traffic hit the database directly" → `dependency-failure` (single hop, not cascading chain).

---

### 4. `dns`

**Definition:** Incident caused by DNS resolution failures, misconfigurations, propagation delays, or cache poisoning.

**Inclusion criteria:**
- DNS lookup failures or timeouts.
- Zone file errors, missing records, CNAME loops.
- DNS propagation delays after migration.

**Exclusion criteria:**
- Network partitions that happen to affect DNS traffic → `network-partition`.
- DNS TTL misconfiguration as part of a broader config change → may co-occur with `config-change`.

**Positive examples:**
1. "The CNAME record was pointing to a decommissioned load balancer, causing all traffic to fail DNS resolution."
2. "A zone transfer failure caused stale DNS records to be served for 4 hours."

**Near-miss:** "The CDN provider's DNS was unreachable due to a DDoS attack" → `dependency-failure` (external provider failure).

---

### 5. `certificate-expiry`

**Definition:** Incident caused by expired, misconfigured, or invalid TLS/SSL certificates.

**Inclusion criteria:**
- Certificate expired and was not renewed.
- Certificate chain incomplete or misconfigured.
- Certificate/key mismatch after rotation.

**Exclusion criteria:**
- Intentional certificate rotation that goes wrong → may co-occur with `config-change`.
- CA compromise or revocation (broader security incident).

**Positive examples:**
1. "The wildcard certificate for *.example.com expired, causing 100% of HTTPS traffic to fail."
2. "After rotating the TLS certificate, the intermediate CA cert was not included, breaking certificate chain validation."

**Near-miss:** "Let's Encrypt rate-limited our renewal requests" → `quota-limit` (the cert didn't expire, renewal was blocked).

---

### 6. `capacity-exhaustion`

**Definition:** Service or infrastructure runs out of a finite resource: CPU, memory, disk, connections, file descriptors, IP addresses, queue depth, or rate limit headroom.

**Inclusion criteria:**
- Resource saturation is the primary cause (disk full, OOM, connection pool exhausted).
- Autoscaling failed to keep up with legitimate load.

**Exclusion criteria:**
- Resource exhaustion caused by retry loops → `retry-storm`.
- Gradual performance degradation with no hard resource limit hit.

**Positive examples:**
1. "The Kafka partition ran out of disk space, causing producers to block and the pipeline to stall."
2. "The connection pool was sized at 50 but peak traffic required 200 connections, causing request queuing and timeouts."

**Near-miss:** "CPU usage climbed to 95% during peak hours but no requests failed" → not an incident (degraded but no impact).

---

### 7. `bad-deploy`

**Definition:** Incident caused by deploying a software artifact (code, container image, binary, migration) that contained a bug, regression, or incompatibility.

**Inclusion criteria:**
- A specific deployment is identified as the trigger.
- Includes rollback as the resolution.
- Database migration failures during deploy.

**Exclusion criteria:**
- Configuration-only changes → `config-change`.
- Infrastructure provisioning (Terraform, CloudFormation) → `config-change`.

**Positive examples:**
1. "Version 2.4.1 introduced a N+1 query that caused the database to become unresponsive under load."
2. "The canary deploy passed health checks but contained a memory leak that caused OOM kills after 2 hours."

**Near-miss:** "A Terraform change removed the security group rule allowing the API to reach the database" → `config-change`.

---

### 8. `dependency-failure`

**Definition:** An external or internal dependency (third-party API, cloud provider service, shared internal service) becomes unavailable or degraded, causing the incident.

**Inclusion criteria:**
- Failure originates in a component the affected team does not own.
- Includes cloud provider outages (AWS, GCP, Azure region failures).
- Shared internal services (auth, payment gateway) failing.

**Exclusion criteria:**
- Failures in components the team owns → use a more specific label.
- Cascading failures where the dependency failure is just the trigger → may co-occur with `cascading-failure`.

**Positive examples:**
1. "AWS us-east-1 experienced an S3 outage, causing all image uploads to fail."
2. "The third-party payment processor returned 500 errors for 30 minutes, blocking all checkouts."

**Near-miss:** "Our internal user service was down" → only `dependency-failure` if the reporting team doesn't own the user service; otherwise use a more specific label.

---

### 9. `network-partition`

**Definition:** Network connectivity failure between components: split-brain, packet loss, BGP issues, VPC/subnet misconfiguration, firewall rule changes.

**Inclusion criteria:**
- Network-level failures (not application-level).
- Split-brain scenarios in distributed systems.
- Firewall or security group changes blocking traffic.

**Exclusion criteria:**
- DNS-specific issues → `dns`.
- Application-level timeouts without network cause.

**Positive examples:**
1. "A BGP misconfiguration caused a network partition between us-east-1a and us-east-1b, splitting the database cluster."
2. "A firewall rule update blocked all traffic between the application VPC and the database VPC."

**Near-miss:** "The service timed out connecting to the database" → needs investigation; timeout alone doesn't confirm network partition.

---

### 10. `database-failure`

**Definition:** Incident caused by database-specific issues: replication lag, failover failures, query performance degradation, lock contention, corruption, or schema migration problems.

**Inclusion criteria:**
- Database engine errors, replication issues, or failover problems.
- Lock contention or deadlocks.
- Query plan changes causing performance cliffs.

**Exclusion criteria:**
- Disk full on DB host → `capacity-exhaustion` (may co-occur).
- Application-level ORM bugs → `bad-deploy`.

**Positive examples:**
1. "A long-running analytical query acquired table-level locks, blocking all writes for 15 minutes."
2. "The primary database failed over to the replica, but the replica was 30 seconds behind, causing data inconsistency."

**Near-miss:** "The application was executing 10,000 queries per page load" → `bad-deploy` (N+1 bug, not a database failure).

---

### 11. `thundering-herd`

**Definition:** A large number of clients or processes simultaneously access a resource after a period of unavailability (cache expiry, service restart, lock release), overwhelming it.

**Inclusion criteria:**
- Cache stampede / cold cache after restart.
- Simultaneous reconnections after a network blip.
- Cron jobs or scheduled tasks all firing at the same instant.

**Exclusion criteria:**
- Sustained high traffic → `capacity-exhaustion`.
- Retry-driven amplification → `retry-storm`.

**Positive examples:**
1. "When the Redis cache restarted, all 500 application instances simultaneously queried the database to repopulate their caches."
2. "A cron job on 200 servers was scheduled at exactly midnight, overwhelming the metrics pipeline."

**Near-miss:** "Traffic increased 3x after a marketing campaign" → `capacity-exhaustion` (gradual, not thundering).

---

### 12. `monitoring-gap`

**Definition:** The incident's impact was prolonged or worsened because monitoring, alerting, or observability was insufficient to detect or diagnose the problem.

**Inclusion criteria:**
- Missing alerts that should have fired.
- Dashboards that didn't cover the failing component.
- Time-to-detection significantly delayed by lack of visibility.

**Exclusion criteria:**
- Monitoring was present but the on-call missed the alert → `human-error`.
- This label captures the systemic gap, not the triggering failure.

**Positive examples:**
1. "No alerts were configured for the queue depth metric, so the backlog grew for 6 hours before a customer reported it."
2. "The new microservice was deployed without any health checks or error rate dashboards."

**Near-miss:** "The alert fired but the on-call engineer was in a meeting" → `human-error` (alert existed, response was delayed).

---

### 13. `human-error`

**Definition:** An operator, developer, or SRE made a manual mistake that directly caused or significantly worsened the incident.

**Inclusion criteria:**
- Running a command against the wrong environment (prod vs staging).
- Manually deleting data or resources.
- Ignoring or misinterpreting alerts.

**Exclusion criteria:**
- Automated process doing the wrong thing → `bad-deploy` or `config-change`.
- Systemic process gaps that allowed the error → may co-occur with `monitoring-gap`.

**Positive examples:**
1. "An engineer ran `DROP TABLE users` against the production database instead of staging."
2. "The on-call acknowledged the alert but assumed it was a false positive and went back to sleep."

**Near-miss:** "A script with a bug deleted production data" → `bad-deploy` (automated, not manual).

---

### 14. `data-corruption`

**Definition:** Data integrity was compromised: records lost, silently corrupted, or inconsistent across stores.

**Inclusion criteria:**
- Data loss (permanent deletion, truncation).
- Silent data corruption (wrong values written, encoding issues).
- Consistency violations across replicas or caches.

**Exclusion criteria:**
- Temporary data unavailability during an outage (data intact after recovery).
- Schema migration errors → `database-failure` or `bad-deploy`.

**Positive examples:**
1. "A race condition in the write path caused 50,000 user records to have their email field overwritten with null."
2. "The ETL pipeline silently dropped Unicode characters, corrupting names for non-English users."

**Near-miss:** "The database was unavailable for 2 hours but no data was lost after recovery" → `database-failure` (no corruption).

---

### 15. `quota-limit`

**Definition:** Incident caused by hitting a rate limit, quota, or usage cap imposed by a cloud provider, API, or internal system.

**Inclusion criteria:**
- API rate limits hit (429 responses).
- Cloud provider quotas (instance limits, API call limits).
- Internal rate limiters being too aggressive.

**Exclusion criteria:**
- Resource exhaustion of owned infrastructure → `capacity-exhaustion`.
- Third-party service being down (not rate-limited) → `dependency-failure`.

**Positive examples:**
1. "We hit the GitHub API rate limit during deployment, causing the CI pipeline to fail for all teams."
2. "The AWS EC2 instance limit in us-east-1 prevented autoscaling from launching new instances during peak."

**Near-miss:** "Our Redis instance ran out of memory" → `capacity-exhaustion` (resource exhaustion, not a quota).

---

## Label Application Guidelines

1. **Multi-label is the default.** Most incidents involve 2–3 contributing factors. Apply all that fit.
2. **Root cause first.** If unsure, label the root cause, not the symptom.
3. **Threshold for application:** The label must describe a significant contributing factor, not a tangential mention. "We should improve monitoring" in lessons learned does not earn `monitoring-gap` unless the incident report explicitly states that missing monitoring delayed detection.
4. **ABSTAIN over guess.** If the text doesn't provide enough evidence for a label, don't apply it. Silver labels from weak supervision will have gaps; that's expected.
5. **Near-miss labels:** When two labels are close, prefer the one matching the root cause. Apply both only if both are genuinely contributing factors.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-16 | Initial 15-label taxonomy |
