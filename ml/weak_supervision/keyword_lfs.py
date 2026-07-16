"""Keyword/regex labeling functions for each taxonomy label.

Each LF class returns POSITIVE with a confidence when its pattern matches,
ABSTAIN otherwise. Section-aware: matches in the Root Cause section are
weighted higher (confidence 0.9 vs 0.7 for body-only).
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from ml.weak_supervision.types import IncidentRecord, LFResult, Vote

SECTION_BOOST = 0.9
BODY_CONFIDENCE = 0.7


def _search_sections(record: IncidentRecord, pattern: re.Pattern[str]) -> bool:
    for key in ("root_cause", "root cause", "rootcause"):
        text = record.sections.get(key, "")
        if text and pattern.search(text):
            return True
    return False


def _search_body(record: IncidentRecord, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.search(record.body)) or bool(pattern.search(record.title))


def _apply(record: IncidentRecord, pattern: re.Pattern[str]) -> LFResult:
    if _search_sections(record, pattern):
        return LFResult(vote=Vote.POSITIVE, confidence=SECTION_BOOST)
    if _search_body(record, pattern):
        return LFResult(vote=Vote.POSITIVE, confidence=BODY_CONFIDENCE)
    return LFResult(vote=Vote.ABSTAIN)


@dataclass(frozen=True)
class KeywordLF:
    """A regex-based labeling function."""

    name: str
    label: str
    pattern: re.Pattern[str]

    def __call__(self, record: IncidentRecord) -> LFResult:
        return _apply(record, self.pattern)


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


lf_config_change = KeywordLF(
    name="kw_config_change",
    label="config-change",
    pattern=_compile(
        r"(?:mis)?config(?:uration)?[\s\-](?:change|error|update|flag|wrong|incorrect)"
        r"|feature[\s\-]?flag.*(?:wrong|incorrect|misconfigured)"
        r"|environment[\s\-]?variable.*(?:wrong|incorrect|missing)"
        r"|config(?:uration)?.*(?:caused|triggered|resulted)"
    ),
)

lf_retry_storm = KeywordLF(
    name="kw_retry_storm",
    label="retry-storm",
    pattern=_compile(
        r"retry[\s\-]?(?:storm|amplif|flood|loop|avalanche)"
        r"|(?:amplif|storm|thunder).*retr(?:y|ied|ies)"
        r"|retr(?:y|ied|ies).*(?:overwhelm|flood|amplif|exacerbat)"
        r"|exponential.*retr(?:y|ies).*(?:no|without|missing).*backoff"
    ),
)

lf_cascading_failure = KeywordLF(
    name="kw_cascading_failure",
    label="cascading-failure",
    pattern=_compile(
        r"cascad(?:e|ing)[\s\-]?fail"
        r"|failure.*propagat"
        r"|(?:chain|domino)[\s\-]?(?:of[\s\-]?)?fail"
        r"|(?:upstream|downstream).*fail.*(?:caused|led|result)"
        r"|thread[\s\-]?pool.*exhaust.*(?:propagat|spread|upstream)"
    ),
)

lf_dns = KeywordLF(
    name="kw_dns",
    label="dns",
    pattern=_compile(
        r"dns[\s\-]?(?:resol|lookup|failure|timeout|propagat|outage|misconfigur|issue)"
        r"|(?:cname|zone[\s\-]?file|zone[\s\-]?transfer|name[\s\-]?server).*(?:fail|error|wrong)"
        r"|(?:resol|lookup).*(?:fail|timeout).*(?:dns|domain|hostname)"
        r"|dns[\s\-]?record"
    ),
)

lf_certificate_expiry = KeywordLF(
    name="kw_certificate_expiry",
    label="certificate-expiry",
    pattern=_compile(
        r"certif(?:icate)?.*(?:expir|invalid|mismatch|chain|renew)"
        r"|(?:tls|ssl|https?).*(?:expir|invalid|mismatch)"
        r"|expir.*certif"
        r"|(?:x509|pkix|certificate[\s\-]?chain).*(?:error|fail|invalid)"
    ),
)

lf_capacity_exhaustion = KeywordLF(
    name="kw_capacity_exhaustion",
    label="capacity-exhaustion",
    pattern=_compile(
        r"(?:disk|storage|memory|cpu|connection[\s\-]?pool|file[\s\-]?descriptor).*"
        r"(?:exhaust|full|limit|saturat|ran[\s\-]?out|oom|out[\s\-]?of)"
        r"|out[\s\-]?of[\s\-]?(?:memory|disk|space|capacity)"
        r"|oom[\s\-]?(?:kill|error)"
        r"|(?:auto[\s\-]?scal|scale[\s\-]?(?:up|out)).*(?:fail|unable|too[\s\-]?slow)"
    ),
)

lf_bad_deploy = KeywordLF(
    name="kw_bad_deploy",
    label="bad-deploy",
    pattern=_compile(
        r"(?:deploy|release|rollout|push).*(?:caus|trigger|introduc|contain|had).*"
        r"(?:bug|regression|error|issue|failure)"
        r"|roll(?:back|ing[\s\-]?back).*(?:resolv|fix|mitigat|restor)"
        r"|(?:canary|blue[\s\-]?green|rolling).*(?:fail|bad|broke)"
        r"|bad[\s\-]?(?:deploy|release|push|build)"
    ),
)

lf_dependency_failure = KeywordLF(
    name="kw_dependency_failure",
    label="dependency-failure",
    pattern=_compile(
        r"(?:aws|gcp|azure|cloud[\s\-]?provider|third[\s\-]?party|external|upstream[\s\-]?service)"
        r".*(?:outage|down|unavail|fail|error|degrad)"
        r"|(?:outage|failure).*(?:aws|gcp|azure|cloud[\s\-]?provider|third[\s\-]?party)"
        r"|(?:s3|ec2|rds|lambda|dynamo|cloudfront|route[\s\-]?53).*(?:outage|fail|unavail)"
    ),
)

lf_network_partition = KeywordLF(
    name="kw_network_partition",
    label="network-partition",
    pattern=_compile(
        r"network[\s\-]?partition"
        r"|split[\s\-]?brain"
        r"|bgp.*(?:misconfigur|error|leak|hijack)"
        r"|(?:vpc|subnet|security[\s\-]?group|firewall).*(?:block|reject|deny|misconfigur)"
        r"|packet[\s\-]?(?:loss|drop).*(?:significan|major|complet)"
    ),
)

lf_database_failure = KeywordLF(
    name="kw_database_failure",
    label="database-failure",
    pattern=_compile(
        r"(?:database|db|postgres|mysql|mongo|redis|cassandra)[\s\-]?"
        r"(?:fail|crash|deadlock|lock[\s\-]?contention|replication[\s\-]?lag|failover|corrupt)"
        r"|(?:deadlock|lock[\s\-]?contention|replication[\s\-]?lag).*(?:database|db)"
        r"|(?:primary|master|leader)[\s\-]?(?:database|db).*fail"
        r"|failover.*(?:database|db|replica)"
    ),
)

lf_thundering_herd = KeywordLF(
    name="kw_thundering_herd",
    label="thundering-herd",
    pattern=_compile(
        r"thunder(?:ing)?[\s\-]?herd"
        r"|cache[\s\-]?(?:stampede|avalanche|thundering)"
        r"|(?:cold[\s\-]?cache|cache[\s\-]?miss).*(?:overwhelm|flood|spike)"
        r"|(?:simultaneous|all[\s\-]?at[\s\-]?once).*(?:reconnect|request|query).*(?:overwhelm|flood)"
    ),
)

lf_monitoring_gap = KeywordLF(
    name="kw_monitoring_gap",
    label="monitoring-gap",
    pattern=_compile(
        r"no[\s\-]?(?:alert|monitor|dashboard|metric|observ)"
        r"|(?:alert|monitor|dashboard|metric).*(?:missing|absent|didn.t[\s\-]?exist|not[\s\-]?set[\s\-]?up)"
        r"|(?:detect|discover).*(?:hours?|days?)[\s\-]?later"
        r"|lack(?:ed)?[\s\-]?(?:of[\s\-]?)?(?:monitor|alert|observ|visib)"
    ),
)

lf_human_error = KeywordLF(
    name="kw_human_error",
    label="human-error",
    pattern=_compile(
        r"human[\s\-]?error"
        r"|(?:operator|engineer|admin|sre|developer).*(?:accident|mistake|wrong|incorrect|inadvert)"
        r"|(?:ran|executed|typed|entered).*(?:wrong|incorrect|production[\s\-]?instead)"
        r"|(?:manual|accidentally).*(?:delet|drop|remov|kill|terminat)"
    ),
)

lf_data_corruption = KeywordLF(
    name="kw_data_corruption",
    label="data-corruption",
    pattern=_compile(
        r"data[\s\-]?(?:corrupt|loss|integrity|inconsisten)"
        r"|(?:corrupt|lost|missing|inconsistent)[\s\-]?data"
        r"|(?:race[\s\-]?condition|write[\s\-]?conflict).*(?:corrupt|overwr|inconsisten)"
        r"|silent(?:ly)?[\s\-]?(?:corrupt|drop|truncat|overwr)"
    ),
)

lf_quota_limit = KeywordLF(
    name="kw_quota_limit",
    label="quota-limit",
    pattern=_compile(
        r"(?:rate|api)[\s\-]?limit.*(?:hit|reach|exceed|block|throttl)"
        r"|(?:quota|usage[\s\-]?cap|usage[\s\-]?limit).*(?:hit|reach|exceed)"
        r"|429.*(?:too[\s\-]?many|rate[\s\-]?limit|throttl)"
        r"|(?:instance|resource)[\s\-]?limit.*(?:prevent|block|unable)"
    ),
)


ALL_KEYWORD_LFS: list[KeywordLF] = [
    lf_config_change,
    lf_retry_storm,
    lf_cascading_failure,
    lf_dns,
    lf_certificate_expiry,
    lf_capacity_exhaustion,
    lf_bad_deploy,
    lf_dependency_failure,
    lf_network_partition,
    lf_database_failure,
    lf_thundering_herd,
    lf_monitoring_gap,
    lf_human_error,
    lf_data_corruption,
    lf_quota_limit,
]
