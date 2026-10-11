CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT
);

CREATE TABLE IF NOT EXISTS schema_registry (
    id SERIAL PRIMARY KEY,
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL REFERENCES schema_versions(version),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (field_name, schema_version)
);

INSERT INTO schema_versions (version, description)
VALUES (1, 'initial schema')
ON CONFLICT (version) DO NOTHING;