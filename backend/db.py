import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv, dotenv_values

ENV_PATH = Path(__file__).resolve().parent / '.env'
load_dotenv(ENV_PATH)


def get_db_connection(database=None):
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=database or os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", "3306")),
        connection_timeout=10,
    )


def get_auth_db_connection():
    # A running dev server may predate the authentication-database migration.
    # Read the new file setting when no process override was loaded at startup.
    auth_database = os.environ.get('DB_AUTH_NAME') or dotenv_values(ENV_PATH).get('DB_AUTH_NAME')
    return get_db_connection(auth_database or os.environ.get('DB_NAME'))
