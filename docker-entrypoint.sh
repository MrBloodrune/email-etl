#!/bin/bash
set -e

# Email ETL Docker Entrypoint Script

# Function to wait for PostgreSQL
wait_for_postgres() {
    echo "Waiting for PostgreSQL to be ready..."
    until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
        echo "PostgreSQL is unavailable - sleeping"
        sleep 2
    done
    echo "PostgreSQL is ready!"
}

# Function to check if database is initialized
check_db_initialized() {
    PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'emails');" | grep -q 't'
}

# Function to initialize database
init_database() {
    echo "Initializing database schema..."
    
    # Run init script
    if [ -f "/app/scripts/init_db.sql" ]; then
        echo "Running init_db.sql..."
        PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /app/scripts/init_db.sql
    fi
    
    # Run migration script
    if [ -f "/app/scripts/migrate_providers.sql" ]; then
        echo "Running migrate_providers.sql..."
        PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /app/scripts/migrate_providers.sql
    fi
    
    echo "Database initialization complete!"
}

# Main entrypoint logic
case "$1" in
    "api")
        wait_for_postgres
        echo "Starting API server..."
        exec python api_server.py
        ;;
    
    "etl")
        wait_for_postgres
        if ! check_db_initialized; then
            init_database
        fi
        echo "Starting ETL worker..."
        # For now, just keep the container running
        # In production, this could run a scheduler like celery or cron
        exec sleep infinity
        ;;
    
    "cli")
        wait_for_postgres
        if ! check_db_initialized; then
            init_database
        fi
        echo "Starting interactive CLI..."
        exec /bin/bash
        ;;
    
    "init-db")
        wait_for_postgres
        init_database
        echo "Database initialization complete!"
        ;;
    
    "python")
        wait_for_postgres
        exec "$@"
        ;;
    
    *)
        # Pass through any other commands
        exec "$@"
        ;;
esac