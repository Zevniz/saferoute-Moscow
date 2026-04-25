import os

class Settings:
    PROJECT_NAME: str = "SafeRoute Engine"
    POSTGRES_URL: str = os.getenv("DATABASE_URL", "postgresql://saferoute:saferoute_pass@db:5432/saferoute_db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
settings = Settings()
