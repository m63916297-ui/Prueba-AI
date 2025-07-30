#!/usr/bin/env python3
"""
Database initialization script for Technical Documentation Agent
"""

import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.database.database import create_tables, engine
from app.database.models import Base
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize the database with all tables"""
    try:
        logger.info("Creating database tables...")
        create_tables()
        logger.info("Database tables created successfully!")
        
        # Verify tables were created
        inspector = engine.dialect.inspector(engine)
        tables = inspector.get_table_names()
        logger.info(f"Created tables: {tables}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        return False


def main():
    """Main function"""
    logger.info("Starting database initialization...")
    
    # Check if database URL is configured
    if not settings.database_url:
        logger.error("Database URL not configured!")
        return False
    
    logger.info(f"Using database: {settings.database_url}")
    
    # Initialize database
    success = init_database()
    
    if success:
        logger.info("Database initialization completed successfully!")
        return True
    else:
        logger.error("Database initialization failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 