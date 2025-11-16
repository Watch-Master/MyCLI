import mysql.connector
from mysql.connector import Error
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import re 

# --- Configuration ---
# !!! IMPORTANT: Update these credentials to match your MySQL setup !!!
# If the table isn't being created, double-check that your MySQL server is running 
# and these 'user' and 'password' values are correct for your local setup.
DB_CONFIG = {
    'host': 'localhost',
    'user': 'myserver2py',  # e.g., 'root'
    'password': 'Myserver@2py', # e.g., 'password123'
    'database': 'student_data_db' # Database will be created if it doesn't exist
}

TABLE_NAME = 'students'
SUBJECTS = ["Physics", "Chemistry", "Maths", "English", "I.P"]

# --- SQL Generation and Column Helpers ---

def get_expected_columns(subjects):
    """Generates the list of required column names for DB and CSV validation."""
    cols = ['name', 'grade', 'section']
    for term in [1, 2]:
        for subject in subjects:
            # Must use the same sanitization logic as the table creation
            safe_subject_name = re.sub(r'[^\w]+', '', subject.lower())
            cols.append(f't{term}_{safe_subject_name}')
    return cols

def get_create_table_sql(table_name, subjects):
    """Dynamically generates the SQL CREATE TABLE statement."""
    marks_columns = []
    for term in [1, 2]:
        for subject in subjects:
            safe_subject_name = re.sub(r'[^\w]+', '', subject.lower())
            col_name = f't{term}_{safe_subject_name}'
            marks_columns.append(f"{col_name} INT NOT NULL")
    
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        grade INT NOT NULL,
        section VARCHAR(10) NOT NULL,
        {', '.join(marks_columns)}
    )
    """
    return create_table_sql


# --- Database Connection and Setup ---

def connect_db(use_db=True):
    """Establishes a connection to the MySQL server."""
    config = DB_CONFIG.copy()
    db_name = DB_CONFIG.get('database', 'N/A')
    
    if not use_db:
        if 'database' in config:
            del config['database']
    
    try:
        conn = mysql.connector.connect(**config)
        return conn
    except Error as e:
        print("\n" + "="*70)
        print("[CRITICAL CONNECTION ERROR]")
        print("The application failed to connect to your MySQL server.")
        print("Error details:", e)
        print("\nACTION REQUIRED: Please check the following:")
        print(f"1. Is your **MySQL server** (e.g., XAMPP, MySQL Workbench) **running**?")
        print(f"2. Are the **DB_CONFIG** credentials in the script correct?")
        print(f"   - Host: {DB_CONFIG.get('host')}")
        print(f"   - User: {DB_CONFIG.get('user')}")
        print(f"   - Password: {DB_CONFIG.get('password')}")
        if use_db:
             print(f"3. Check connection to database: '{db_name}'.")
        print("="*70)
        return None 

def setup_database():
    """Creates the database and the required table if they don't exist."""
    print("-> Setting up database...")
    db_name = DB_CONFIG['database']
    
    # 1. Connect without specifying the database name
    conn_no_db = connect_db(use_db=False)
    if conn_no_db is None:
        return False

    cursor = conn_no_db.cursor()
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.close()
        conn_no_db.close()
    except Error as e:
        print(f"[ERROR] Failed to create database '{db_name}': {e}")
        return False
        
    # 2. Connect with the database name
    conn = connect_db(use_db=True)
    if conn is None:
        print(f"[CRITICAL SETUP ABORTED] Could not connect to database '{db_name}' after creation.")
        return False
    
    cursor = conn.cursor()

    try:
        create_table_sql = get_create_table_sql(TABLE_NAME, SUBJECTS)
        cursor.execute(create_table_sql)
        conn.commit()
        print(f"-> Database '{db_name}' and table '{TABLE_NAME}' are ready.")

    except Error as e:
        print(f"[CRITICAL ERROR] Failed to create table: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    return True


# --- Data Handling Functions ---

def get_mark_input(prompt):
    """Safely gets and validates mark input."""
    while True:
        try:
            mark = int(input(prompt))
            if 0 <= mark <= 100:
                return mark
            else:
                print("Marks must be between 0 and 100.")
        except ValueError:
            print("Invalid input. Please enter a whole number.")

def add_student():
    """Prompts user for student data and inserts it into MySQL."""
    print("\n--- Add New Student Record (Manual) ---")
    
    name = input("Enter student name: ").strip()
    try:
        grade = int(input("Enter student grade (1-12): "))
    except ValueError:
        print("[ERROR] Grade must be a number.")
        return
        
    section = input("Enter student section (e.g., A, B): ").strip().upper()

    if not all([name, grade, section]) or not (1 <= grade <= 12):
        print("[ERROR] Invalid input provided.")
        return

    marks = {}
    columns_from_marks = []
    
    print("\n--- Enter Term 1 Marks (0-100) ---")
    for subject in SUBJECTS:
        safe_subject_name = re.sub(r'[^\w]+', '', subject.lower())
        col_name = f't1_{safe_subject_name}'
        marks[col_name] = get_mark_input(f"{subject}: ")
        columns_from_marks.append(col_name)

    print("\n--- Enter Term 2 Marks (0-100) ---")
    for subject in SUBJECTS:
        safe_subject_name = re.sub(r'[^\w]+', '', subject.lower())
        col_name = f't2_{safe_subject_name}'
        marks[col_name] = get_mark_input(f"{subject}: ")
        columns_from_marks.append(col_name)

    conn = connect_db()
    if conn is None:
        print("[ERROR] Data insertion failed. Cannot connect to database.")
        return

    cursor = conn.cursor()

    columns = ['name', 'grade', 'section'] + columns_from_marks
    placeholders = ['%s'] * len(columns)
    
    insert_sql = f"""
    INSERT INTO {TABLE_NAME} ({', '.join(columns)}) 
    VALUES ({', '.join(placeholders)})
    """
    
    values = (name, grade, section) + tuple(marks[col] for col in columns_from_marks)

    try:
        cursor.execute(insert_sql, values)
        conn.commit()
        print(f"\n[SUCCESS] Student '{name}' added successfully.")
    except Error as e:
        print(f"\n[ERROR] Failed to insert data: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def import_data_from_csv():
    """Reads data from a CSV file and inserts records into the database."""
    print("\n--- Import Data from CSV ---")
    file_path = input("Enter the path to the CSV file (e.g., data.csv): ").strip()
    
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found at path: {file_path}")
        return

    try:
        # 1. Read CSV using Pandas
        df = pd.read_csv(file_path)
        print(f"[INFO] Loaded {len(df)} rows from CSV.")
        
        # 2. Validation
        required_cols = set(get_expected_columns(SUBJECTS))
        df_cols = set(df.columns.map(str.lower)) # Check against lowercased column names from CSV
        
        missing_cols = required_cols - df_cols
        if missing_cols:
            print(f"[ERROR] CSV is missing required columns: {', '.join(missing_cols)}")
            print("Please ensure your CSV headers match the database schema exactly.")
            return

        # Prepare for insertion
        conn = connect_db()
        if conn is None:
            print("[ERROR] Import failed. Cannot connect to database.")
            return
        
        cursor = conn.cursor()
        
        # Use the required columns list to construct the SQL query dynamically
        insert_columns = get_expected_columns(SUBJECTS)
        placeholders = ', '.join(['%s'] * len(insert_columns))
        insert_sql = f"INSERT INTO {TABLE_NAME} ({', '.join(insert_columns)}) VALUES ({placeholders})"
        
        success_count = 0
        
        # 3. Iterate and Insert
        # Convert DataFrame rows to a list of tuples in the required order
        records = df[insert_columns].values.tolist()
        
        for record in records:
            try:
                # Use execute with the single record tuple
                cursor.execute(insert_sql, tuple(record))
                success_count += 1
            except Error as e:
                print(f"[WARNING] Failed to insert record (Name: {record[0]}). Skipping. Error: {e}")

        conn.commit()
        print(f"\n[SUCCESS] Successfully imported {success_count} records from '{file_path}'.")

    except pd.errors.EmptyDataError:
        print("[ERROR] The CSV file is empty.")
    except pd.errors.ParserError:
        print("[ERROR] Could not parse the CSV file. Check formatting.")
    except Exception as e:
        print(f"[CRITICAL ERROR] An unexpected error occurred during import: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- Data Retrieval, Calculation, and Visualization Functions (Unchanged) ---

def retrieve_data_to_pandas():
    """Retrieves all student data from MySQL and loads it into a Pandas DataFrame."""
    print("\n--- Retrieving Data ---")
    conn = connect_db()
    if conn is None:
        print("[ERROR] Data retrieval failed. Cannot connect to database.")
        return pd.DataFrame()
    
    try:
        query = f"SELECT * FROM {TABLE_NAME}"
        df = pd.read_sql(query, conn)
        print(f"[SUCCESS] Loaded {len(df)} records into Pandas DataFrame.")
        return df
    except pd.io.sql.DatabaseError as e:
        print(f"[ERROR] Could not retrieve data from table. Check if table '{TABLE_NAME}' was created successfully: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during retrieval: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def calculate_and_view_averages(df):
    """Calculates total marks and average percentage for Term 1 and Term 2 and prints a summary table."""
    if df.empty:
        print("\n[INFO] No data available to calculate averages.")
        return

    print("\n--- Student Performance Averages ---")
    
    num_subjects = len(SUBJECTS)
    max_score = num_subjects * 100
    
    df['Term 1 Total'] = df.filter(regex='^t1_').sum(axis=1)
    df['Term 2 Total'] = df.filter(regex='^t2_').sum(axis=1)

    df['Avg Term 1 (%)'] = (df['Term 1 Total'] / max_score * 100).round(2)
    df['Avg Term 2 (%)'] = (df['Term 2 Total'] / max_score * 100).round(2)

    summary_df = df[['name', 'grade', 'section', 'Term 1 Total', 'Avg Term 1 (%)', 'Term 2 Total', 'Avg Term 2 (%)']]
    
    print("\nSummary Table (Max Score per Term: 500):")
    print(summary_df.to_string(index=False))

def export_to_csv(df):
    """Exports the Pandas DataFrame to a CSV file."""
    if df.empty:
        print("\n[INFO] No data to export.")
        return
    
    filename = 'student_records.csv'
    try:
        df['Term 1 Total'] = df.filter(regex='^t1_').sum(axis=1)
        df['Term 2 Total'] = df.filter(regex='^t2_').sum(axis=1)

        df.drop(columns=['id'], errors='ignore').to_csv(filename, index=False)
        print(f"\n[SUCCESS] Data exported to '{os.path.abspath(filename)}'")
        print(f"Exported {len(df)} records, including calculated totals.")
    except Exception as e:
        print(f"[ERROR] Failed to export data to CSV: {e}")

def view_graph(df):
    """Generates a Matplotlib bar chart comparing Term 1 and Term 2 average percentages."""
    if df.empty:
        print("\n[INFO] No data available for graphing.")
        return

    print("\n--- Generating Performance Graph (Average Percentage) ---")
    
    num_subjects = len(SUBJECTS)
    max_score = num_subjects * 100
    
    df['Term 1 Total'] = df.filter(regex='^t1_').sum(axis=1)
    df['Term 2 Total'] = df.filter(regex='^t2_').sum(axis=1)
    df['Avg Term 1 (%)'] = (df['Term 1 Total'] / max_score * 100).round(2)
    df['Avg Term 2 (%)'] = (df['Term 2 Total'] / max_score * 100).round(2)
    
    df['Label'] = df['name'] + ' (' + df['grade'].astype(str) + '-' + df['section'] + ')'

    X_axis = range(len(df))
    width = 0.35
    
    plt.figure(figsize=(12, 6))
    
    plt.bar([x - width/2 for x in X_axis], df['Avg Term 1 (%)'], width, label='Term 1 Average (%)', color='skyblue')
    plt.bar([x + width/2 for x in X_axis], df['Avg Term 2 (%)'], width, label='Term 2 Average (%)', color='salmon')

    plt.xticks(X_axis, df['Label'], rotation=45, ha='right')
    plt.ylim(0, 105) 
    plt.yticks(range(0, 101, 10)) 
    plt.ylabel('Average Percentage Score (%)')
    plt.title('Student Term 1 vs Term 2 Average Performance')
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    print("-> Displaying graph in a new window. Close the window to continue.")
    plt.show()


# --- Main CLI Loop ---

def main():
    """Main function to run the student data manager CLI."""
    
    if setup_database() is False:
        return

    while True:
        print("\n" + "="*50)
        print("Student Data Manager CLI")
        print("="*50)
        print("1. Import Records from CSV File")
        print("2. Add New Student Data (Manual)")
        print("3. Calculate and View Averages (using Pandas)")
        print("4. Retrieve Data & Export to CSV (using Pandas)")
        print("5. Retrieve Data & View Graph (using Matplotlib)")
        print("6. Exit")
        print("="*50)
        
        try:
            choice = input("Enter your choice (1-6): ")
        except EOFError:
            print("\nInput stream closed. Exiting.")
            break
        except KeyboardInterrupt:
            print("\nExiting application. Goodbye!")
            break
        
        if choice == '1':
            import_data_from_csv()
        
        elif choice == '2':
            add_student()
        
        elif choice == '3':
            data_frame = retrieve_data_to_pandas()
            if not data_frame.empty:
                calculate_and_view_averages(data_frame)
        
        elif choice == '4':
            data_frame = retrieve_data_to_pandas()
            if not data_frame.empty:
                export_to_csv(data_frame)
        
        elif choice == '5':
            data_frame = retrieve_data_to_pandas()
            if not data_frame.empty:
                view_graph(data_frame)

        elif choice == '6':
            print("Exiting application. Goodbye!")
            break
            
        else:
            print("[INFO] Invalid choice. Please enter a number between 1 and 6.")

if __name__ == "__main__":
    main()
