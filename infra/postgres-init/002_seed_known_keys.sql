INSERT INTO schema_registry (field_name, field_type, schema_version)
VALUES ('browser', 'string', 1), ('referrer', 'string', 1)
ON CONFLICT (field_name, schema_version) DO NOTHING; 