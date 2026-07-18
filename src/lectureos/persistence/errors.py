"""Minimal public failures for durable persistence boundaries."""


class PersistenceError(RuntimeError):
    pass


class PersistenceIdentityCollisionError(PersistenceError):
    pass


class UnsupportedSchemaVersionError(PersistenceError):
    pass


class SchemaFeatureUnavailableError(PersistenceError):
    pass
