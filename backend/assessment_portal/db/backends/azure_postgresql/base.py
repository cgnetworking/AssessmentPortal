from django.db.backends.postgresql.base import DatabaseWrapper as PostgreSqlDatabaseWrapper

from assessment_portal.azure_postgres import get_postgres_access_token, validate_remote_postgres_host


class DatabaseWrapper(PostgreSqlDatabaseWrapper):
    def get_connection_params(self):
        params = super().get_connection_params()
        validate_remote_postgres_host(params.get("host") or self.settings_dict.get("HOST"))
        params["password"] = get_postgres_access_token()
        return params
