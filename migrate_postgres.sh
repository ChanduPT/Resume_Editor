#!/bin/bash
# Quick setup script for PostgreSQL migration

echo "========================================="
echo "PostgreSQL Format Column Migration"
echo "========================================="
echo ""
echo "Please enter your PostgreSQL connection details:"
echo ""

read -p "Host (default: localhost): " DB_HOST
DB_HOST=${DB_HOST:-localhost}

read -p "Port (default: 5432): " DB_PORT
DB_PORT=${DB_PORT:-5432}

read -p "Database name: " DB_NAME

read -p "Username: " DB_USER

read -sp "Password: " DB_PASSWORD
echo ""

# Construct DATABASE_URL
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo ""
echo "Connecting to: postgresql://${DB_USER}:***@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo ""

# Run migration
python3 scripts/add_format_column.py

echo ""
echo "========================================="
echo "To make this permanent, add to your shell:"
echo "export DATABASE_URL=\"postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}\""
echo "========================================="
