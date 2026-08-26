import os
import typing

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "0.1.0"
    APP_TITLE: str = "精进日志"
    PROJECT_NAME: str = "精进日志"
    APP_DESCRIPTION: str = "Description"

    CORS_ORIGINS: typing.List = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: typing.List = ["*"]
    CORS_ALLOW_HEADERS: typing.List = ["*"]

    DEBUG: bool = True

    PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    BASE_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir))
    LOGS_ROOT: str = os.path.join(BASE_DIR, "app/logs")
    SECRET_KEY: str = "3488a63e1765035d386f05409663f55c83bfae3b3c61a932744b20ad14244dcf"  # openssl rand -hex 32
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 day
    # 微信小程序凭据，务必通过环境变量注入，不要把真实值写进代码
    WX_APPID: str = os.getenv("WX_APPID", "")
    WX_SECRET: str = os.getenv("WX_SECRET", "")
    MINIPROGRAM_ROLE_NAME: str = "小程序用户"
    TORTOISE_ORM: dict = {
        "connections": {
            # SQLite configuration
            # "sqlite": {
            #     "engine": "tortoise.backends.sqlite",
            #     "credentials": {"file_path": f"{BASE_DIR}/db.sqlite3"},  # Path to SQLite database file
            # },
            # MySQL/MariaDB configuration
            # Install with: tortoise-orm[asyncmy]
            "mysql": {
                "engine": "tortoise.backends.mysql",
                "credentials": {
                    "host": os.getenv("DB_HOST", "localhost"),
                    "port": int(os.getenv("DB_PORT", "3306")),
                    "user": os.getenv("DB_USER", "root"),
                    "password": os.getenv("DB_PASSWORD", "chRDW=2021"),
                    "database": os.getenv("DB_NAME", "plan"),
                },
                # "credentials": {
                #     "host": "localhost",  # Database host address
                #     "port": 3306,  # Database port
                #     "user": "root",  # Database username
                #     "password": "chRDW=2021",  # Database password
                #     "database": "plan",  # Database name
                # },
            },
            # PostgreSQL configuration
            # Install with: tortoise-orm[asyncpg]
            # "postgres": {
            #     "engine": "tortoise.backends.asyncpg",
            #     "credentials": {
            #         "host": "localhost",  # Database host address
            #         "port": 5432,  # Database port
            #         "user": "yourusername",  # Database username
            #         "password": "yourpassword",  # Database password
            #         "database": "yourdatabase",  # Database name
            #     },
            # },
            # MSSQL/Oracle configuration
            # Install with: tortoise-orm[asyncodbc]
            # "oracle": {
            #     "engine": "tortoise.backends.asyncodbc",
            #     "credentials": {
            #         "host": "localhost",  # Database host address
            #         "port": 1433,  # Database port
            #         "user": "yourusername",  # Database username
            #         "password": "yourpassword",  # Database password
            #         "database": "yourdatabase",  # Database name
            #     },
            # },
            # SQLServer configuration
            # Install with: tortoise-orm[asyncodbc]
            # "sqlserver": {
            #     "engine": "tortoise.backends.asyncodbc",
            #     "credentials": {
            #         "host": "localhost",  # Database host address
            #         "port": 1433,  # Database port
            #         "user": "yourusername",  # Database username
            #         "password": "yourpassword",  # Database password
            #         "database": "yourdatabase",  # Database name
            #     },
            # },
        },
        "apps": {
            "models": {
                "models": ["app.models", "aerich.models"],
                "default_connection": "mysql",
            },
        },
        "use_tz": False,  # Whether to use timezone-aware datetimes
        "timezone": "Asia/Shanghai",  # Timezone setting
    }
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"


settings = Settings()
