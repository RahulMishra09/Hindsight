# ADR-0002: Redis Streams over Kafka

**Date:** 2026-07-04
**Status:** Accepted
**Deciders:** Core team

---

## Context

The Hindsight ML pipeline is inherently asynchronous: after an incident is ingested, it must pass through classification, embedding, and deduplication workers before being marked complete. These stages need to be decoupled so that:

- A slow model inference step does not block the API.
- Workers can be scaled independently.
- At-least-once delivery is guaranteed (workers restart without losing messages).
- Reprocessing a message that has already been handled is safe (idempotency via `content_hash`).

We need to choose an event bus / message queue.

### Options Considered

**Option A: Redis 7 Streams with consumer groups**
Use Redis's built-in `XADD` / `XREADGROUP` / `XACK` primitives. Redis is already required for caching.

**Option B: Apache Kafka**
Distributed log with consumer groups, high throughput, strong ordering guarantees.

**Option C: RabbitMQ**
Traditional AMQP message broker with routing, exchanges, and dead-letter queues.

**Option D: In-process asyncio queues (`asyncio.Queue`)**
No external broker; workers run as coroutines within the same process.

**Option E: Celery + Redis/RabbitMQ**
Celery task queue abstraction on top of a broker.

---

## Decision

**Option A: Redis 7 Streams with consumer groups.**

---

## Rationale

### Why Redis Streams over Kafka

1. **Infrastructure already present.** Redis is required for API-layer caching and rate limiting. Reusing it for the event bus adds zero new infrastructure. Kafka requires a separate cluster (or at minimum a KRaft/Zookeeper node) — significant operational overhead for v1 single-node deployment.

2. **Throughput match.** Hindsight v1 targets < 1,000 incident ingestions per day. Redis Streams handles millions of messages per second. Kafka's advantages (log compaction, multi-partition parallelism, replication) are irrelevant at this scale.

3. **Consumer group semantics.** Redis 7 Streams supports consumer groups with `XREADGROUP` (competitive consumption), `XACK` (explicit acknowledgement), and `XAUTOCLAIM` (automatic redelivery on consumer crash). This is exactly the at-least-once delivery semantics we need.

4. **Operational simplicity.** A Redis Streams consumer is a handful of async calls. Kafka requires a Kafka client library (`confluent-kafka` or `aiokafka`), topic creation, partition management, and offset tracking. Redis Streams requires only `aioredis`.

### Why not RabbitMQ

RabbitMQ is a solid choice but adds another service to operate alongside Redis. The routing/exchange features are not needed for Hindsight's linear pipeline.

### Why not in-process asyncio queues

`asyncio.Queue` cannot survive process restarts. Any worker crash loses all queued messages. This violates the at-least-once delivery requirement.

### Why not Celery

Celery would sit on top of Redis anyway, adding abstraction overhead, a Beat scheduler we don't need, and its own dependency tree. Redis Streams gives us the same guarantees with less indirection, and keeps our workers as plain async Python rather than Celery task functions.

---

## Stream Topology

```
hindsight:ingest       → published by API on successful incident write
hindsight:classify     → published by ingest consumer; consumed by ClassifierWorker
hindsight:embed        → published by ClassifierWorker; consumed by EmbedderWorker
hindsight:deduplicate  → published by EmbedderWorker; consumed by DeduplicatorWorker
hindsight:complete     → published by DeduplicatorWorker (pipeline done)
```

Each worker:
- Belongs to exactly one consumer group (named `<worker-type>-cg`).
- Reads with `XREADGROUP GROUP <cg> <consumer-id> COUNT 10 BLOCK 5000`.
- Writes its result to the DB, then ACKs with `XACK`.
- On crash, Redis holds unacknowledged messages; `XAUTOCLAIM` redelivers after a configurable timeout.

---

## Consequences

- `app/events/` contains `publisher.py` and `consumer.py` (async Redis Streams helpers).
- Each worker in `app/workers/` subclasses `BaseConsumer` from `app/events/consumer.py`.
- No Kafka client, RabbitMQ client, or Celery import appears anywhere in the codebase.
- Integration tests spin up a real `redis:7-alpine` container via testcontainers.
- The explicitly descoped Celery item in CLAUDE.md and SAD.md §3 is a direct consequence of this decision.

### Upgrade Path

If Hindsight outgrows Redis Streams (> 10k events/day, need for log compaction, multi-region replication), the `BaseConsumer` abstraction makes it feasible to swap in Kafka without touching worker logic. This is a v2+ concern.
