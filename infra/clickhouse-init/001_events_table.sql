CREATE TABLE IF NOT EXISTS default.click_events
(
    event_id String,
    event_type String,
    user_id String,
    session_id String,
    url String,
    timestamp DateTime64(3),
    received_at DateTime64(3) DEFAULT now64(3),
    raw_payload String
)
ENGINE = MergeTree
ORDER BY (timestamp, event_id);
