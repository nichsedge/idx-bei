import os
import glob
import json
import pandas as pd
from sqlalchemy import create_engine, text
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("idx_data_import.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# PostgreSQL Configuration
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres'  # Replace with your actual password
}

# Database and table name
DB_NAME = PG_CONFIG['database']
TABLE_NAME = 'financial_ratios'

def create_connection():
    """Create a database connection to PostgreSQL"""
    try:
        engine = create_engine(
            f"postgresql://{PG_CONFIG['user']}:{PG_CONFIG['password']}@{PG_CONFIG['host']}:{PG_CONFIG['port']}/{DB_NAME}"
        )
        logger.info("Database connection established")
        return engine
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL: {e}")
        raise

def process_json_files(data_directory="../data"):
    """Process all JSON files in the specified directory"""
    try:
        # Get all JSON files matching pattern
        json_files = glob.glob(f"{data_directory}/financial_*.json")
        logger.info(f"Found {len(json_files)} JSON files to process")
        
        all_data = []
        
        # Process each file
        for file_path in sorted(json_files):
            logger.info(f"Processing {file_path}")
            with open(file_path, 'r') as file:
                try:
                    json_data = json.load(file)
                    if 'data' in json_data and json_data['data']:
                        all_data.extend(json_data['data'])
                except json.JSONDecodeError:
                    logger.error(f"Error decoding JSON in {file_path}")
                    continue
        
        return all_data
    except Exception as e:
        logger.error(f"Error processing JSON files: {e}")
        raise

def to_snake_case(name):
    import re
    name = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def transform_data_to_dataframe(data):
    """Transform the raw data into a pandas DataFrame"""
    if not data:
        logger.warning("No data to transform")
        return pd.DataFrame()
    
    # Extract the data into a DataFrame
    try:
        df = pd.json_normalize(data)
        
        # Rename columns if they exist in the DataFrame
        df.columns = [to_snake_case(col) for col in df.columns]
        
        # Convert date columns to datetime
        if 'period_date' in df.columns:
            df['period_date'] = pd.to_datetime(df['period_date'])
        
        # Store the original raw data as JSON string
        # df['raw_data'] = data
        
        logger.info(f"Transformed data into DataFrame with {len(df)} rows and {len(df.columns)} columns")
        return df
    except Exception as e:
        logger.error(f"Error transforming data to DataFrame: {e}")
        raise

def load_data_to_postgres(df, engine):
    """Load DataFrame to PostgreSQL database"""
    if df.empty:
        logger.warning("No data to load into PostgreSQL")
        return
    
    try:
        # Load data to PostgreSQL
        df.to_sql(
            name=TABLE_NAME,
            con=engine,
            if_exists='append',
            index=False,
            chunksize=1000,
            method='multi'
        )
        logger.info(f"Successfully loaded {len(df)} rows into {TABLE_NAME}")
    except Exception as e:
        logger.error(f"Error loading data to PostgreSQL: {e}")
        raise

# def main():
    """Main function to run the ETL process"""
try:
    logger.info("Starting ETL process")
    
    # Create connection to PostgreSQL
    engine = create_connection()
    
    # Process JSON files
    data = process_json_files()
    
    # Transform data to DataFrame
    df = transform_data_to_dataframe(data)
    
    # Load data to PostgreSQL
    if not df.empty:
        load_data_to_postgres(df, engine)
    
    logger.info("ETL process completed successfully")
except Exception as e:
    logger.error(f"ETL process failed: {e}")


# main()