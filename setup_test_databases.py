# Test Database Setup Script
import pymysql
import asyncio
from config.settings import settings

class TestDatabaseSetup:
    def __init__(self):
        self.connection_params = {
            'host': settings.MYSQL_HOST,
            'port': settings.MYSQL_PORT,
            'user': settings.MYSQL_USERNAME,
            'password': settings.MYSQL_PASSWORD,
            'charset': 'utf8mb4'
        }
    
    def create_databases(self):
        """Create test databases"""
        try:
            connection = pymysql.connect(**self.connection_params)
            cursor = connection.cursor()
            
            # Create E-commerce database
            cursor.execute("CREATE DATABASE IF NOT EXISTS ecommerce_test")
            print("SUCCESS: Created ecommerce_test database")
            
            # Create Pharma database
            cursor.execute("CREATE DATABASE IF NOT EXISTS pharma_test")
            print("SUCCESS: Created pharma_test database")
            
            connection.commit()
            cursor.close()
            connection.close()
            
            return True
            
        except Exception as e:
            print(f"❌ Database creation failed: {str(e)}")
            return False
    
    def setup_ecommerce_database(self):
        """Setup e-commerce test database with sample data"""
        try:
            connection_params = self.connection_params.copy()
            connection_params['database'] = 'ecommerce_test'
            
            connection = pymysql.connect(**connection_params)
            cursor = connection.cursor()
            
            # Create tables
            tables = {
                'customers': """
                    CREATE TABLE IF NOT EXISTS customers (
                        customer_id INT PRIMARY KEY AUTO_INCREMENT,
                        first_name VARCHAR(50) NOT NULL,
                        last_name VARCHAR(50) NOT NULL,
                        email VARCHAR(100) UNIQUE NOT NULL,
                        phone VARCHAR(20),
                        address TEXT,
                        city VARCHAR(50),
                        state VARCHAR(50),
                        zip_code VARCHAR(10),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """,
                'categories': """
                    CREATE TABLE IF NOT EXISTS categories (
                        category_id INT PRIMARY KEY AUTO_INCREMENT,
                        category_name VARCHAR(100) NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                'products': """
                    CREATE TABLE IF NOT EXISTS products (
                        product_id INT PRIMARY KEY AUTO_INCREMENT,
                        product_name VARCHAR(200) NOT NULL,
                        description TEXT,
                        price DECIMAL(10,2) NOT NULL,
                        category_id INT,
                        stock_quantity INT DEFAULT 0,
                        sku VARCHAR(50) UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (category_id) REFERENCES categories(category_id)
                    )
                """,
                'orders': """
                    CREATE TABLE IF NOT EXISTS orders (
                        order_id INT PRIMARY KEY AUTO_INCREMENT,
                        customer_id INT NOT NULL,
                        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_amount DECIMAL(10,2) NOT NULL,
                        status ENUM('pending', 'processing', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
                        shipping_address TEXT,
                        payment_method VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                    )
                """,
                'order_items': """
                    CREATE TABLE IF NOT EXISTS order_items (
                        order_item_id INT PRIMARY KEY AUTO_INCREMENT,
                        order_id INT NOT NULL,
                        product_id INT NOT NULL,
                        quantity INT NOT NULL,
                        unit_price DECIMAL(10,2) NOT NULL,
                        total_price DECIMAL(10,2) NOT NULL,
                        FOREIGN KEY (order_id) REFERENCES orders(order_id),
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    )
                """,
                'reviews': """
                    CREATE TABLE IF NOT EXISTS reviews (
                        review_id INT PRIMARY KEY AUTO_INCREMENT,
                        customer_id INT NOT NULL,
                        product_id INT NOT NULL,
                        rating INT CHECK (rating >= 1 AND rating <= 5),
                        review_text TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    )
                """,
                'suppliers': """
                    CREATE TABLE IF NOT EXISTS suppliers (
                        supplier_id INT PRIMARY KEY AUTO_INCREMENT,
                        supplier_name VARCHAR(100) NOT NULL,
                        contact_person VARCHAR(100),
                        email VARCHAR(100),
                        phone VARCHAR(20),
                        address TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                'inventory': """
                    CREATE TABLE IF NOT EXISTS inventory (
                        inventory_id INT PRIMARY KEY AUTO_INCREMENT,
                        product_id INT NOT NULL,
                        supplier_id INT,
                        quantity_in_stock INT DEFAULT 0,
                        reorder_level INT DEFAULT 10,
                        last_restocked DATE,
                        FOREIGN KEY (product_id) REFERENCES products(product_id),
                        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
                    )
                """,
                'payments': """
                    CREATE TABLE IF NOT EXISTS payments (
                        payment_id INT PRIMARY KEY AUTO_INCREMENT,
                        order_id INT NOT NULL,
                        payment_method VARCHAR(50) NOT NULL,
                        amount DECIMAL(10,2) NOT NULL,
                        payment_status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
                        transaction_id VARCHAR(100),
                        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (order_id) REFERENCES orders(order_id)
                    )
                """,
                'shipping': """
                    CREATE TABLE IF NOT EXISTS shipping (
                        shipping_id INT PRIMARY KEY AUTO_INCREMENT,
                        order_id INT NOT NULL,
                        tracking_number VARCHAR(100),
                        carrier VARCHAR(50),
                        shipping_address TEXT,
                        shipping_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        estimated_delivery DATE,
                        actual_delivery DATE,
                        status ENUM('pending', 'shipped', 'in_transit', 'delivered') DEFAULT 'pending',
                        FOREIGN KEY (order_id) REFERENCES orders(order_id)
                    )
                """
            }
            
            # Create all tables
            for table_name, create_sql in tables.items():
                cursor.execute(create_sql)
                print(f"SUCCESS: Created table: {table_name}")
            
            # Insert sample data
            self.insert_ecommerce_sample_data(cursor)
            
            connection.commit()
            cursor.close()
            connection.close()
            
            print("SUCCESS: E-commerce database setup completed")
            return True
            
        except Exception as e:
            print(f"ERROR: E-commerce database setup failed: {str(e)}")
            return False
    
    def insert_ecommerce_sample_data(self, cursor):
        """Insert sample data into e-commerce tables"""
        try:
            # Insert categories
            categories_data = [
                ('Electronics', 'Electronic devices and gadgets'),
                ('Clothing', 'Fashion and apparel'),
                ('Books', 'Books and literature'),
                ('Home & Garden', 'Home improvement and gardening'),
                ('Sports', 'Sports equipment and accessories')
            ]
            cursor.executemany(
                "INSERT INTO categories (category_name, description) VALUES (%s, %s)",
                categories_data
            )
            
            # Insert customers
            customers_data = [
                ('John', 'Doe', 'john.doe@email.com', '555-0101', '123 Main St', 'New York', 'NY', '10001'),
                ('Jane', 'Smith', 'jane.smith@email.com', '555-0102', '456 Oak Ave', 'Los Angeles', 'CA', '90210'),
                ('Bob', 'Johnson', 'bob.johnson@email.com', '555-0103', '789 Pine Rd', 'Chicago', 'IL', '60601'),
                ('Alice', 'Brown', 'alice.brown@email.com', '555-0104', '321 Elm St', 'Houston', 'TX', '77001'),
                ('Charlie', 'Wilson', 'charlie.wilson@email.com', '555-0105', '654 Maple Dr', 'Phoenix', 'AZ', '85001')
            ]
            cursor.executemany(
                "INSERT INTO customers (first_name, last_name, email, phone, address, city, state, zip_code) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                customers_data
            )
            
            # Insert products
            products_data = [
                ('iPhone 15', 'Latest Apple smartphone', 999.99, 1, 50, 'IPH15-001'),
                ('Samsung Galaxy S24', 'Android smartphone', 899.99, 1, 30, 'SGS24-001'),
                ('Nike Air Max', 'Running shoes', 129.99, 2, 100, 'NAM-001'),
                ('Adidas T-Shirt', 'Cotton t-shirt', 29.99, 2, 200, 'ATS-001'),
                ('Python Programming Book', 'Learn Python programming', 49.99, 3, 75, 'PPB-001'),
                ('JavaScript Guide', 'Complete JS guide', 39.99, 3, 60, 'JSG-001'),
                ('Garden Hose', '50ft garden hose', 39.99, 4, 40, 'GH-001'),
                ('Tennis Racket', 'Professional tennis racket', 199.99, 5, 25, 'TR-001')
            ]
            cursor.executemany(
                "INSERT INTO products (product_name, description, price, category_id, stock_quantity, sku) VALUES (%s, %s, %s, %s, %s, %s)",
                products_data
            )
            
            # Insert orders
            orders_data = [
                (1, 1299.98, 'delivered', '123 Main St, New York, NY 10001', 'credit_card'),
                (2, 199.98, 'shipped', '456 Oak Ave, Los Angeles, CA 90210', 'paypal'),
                (3, 89.98, 'processing', '789 Pine Rd, Chicago, IL 60601', 'credit_card'),
                (4, 39.99, 'pending', '321 Elm St, Houston, TX 77001', 'credit_card'),
                (5, 199.99, 'delivered', '654 Maple Dr, Phoenix, AZ 85001', 'paypal')
            ]
            cursor.executemany(
                "INSERT INTO orders (customer_id, total_amount, status, shipping_address, payment_method) VALUES (%s, %s, %s, %s, %s)",
                orders_data
            )
            
            # Insert order items
            order_items_data = [
                (1, 1, 1, 999.99, 999.99),
                (1, 3, 1, 129.99, 129.99),
                (2, 4, 2, 29.99, 59.98),
                (2, 5, 1, 49.99, 49.99),
                (3, 6, 1, 39.99, 39.99),
                (3, 7, 1, 39.99, 39.99),
                (4, 8, 1, 39.99, 39.99),
                (5, 8, 1, 199.99, 199.99)
            ]
            cursor.executemany(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price) VALUES (%s, %s, %s, %s, %s)",
                order_items_data
            )
            
            print("SUCCESS: Sample data inserted into e-commerce tables")
            
        except Exception as e:
            print(f"ERROR: Sample data insertion failed: {str(e)}")
    
    def setup_pharma_database(self):
        """Setup pharma test database with sample data"""
        try:
            connection_params = self.connection_params.copy()
            connection_params['database'] = 'pharma_test'
            
            connection = pymysql.connect(**connection_params)
            cursor = connection.cursor()
            
            # Create tables
            tables = {
                'patients': """
                    CREATE TABLE IF NOT EXISTS patients (
                        patient_id INT PRIMARY KEY AUTO_INCREMENT,
                        first_name VARCHAR(50) NOT NULL,
                        last_name VARCHAR(50) NOT NULL,
                        date_of_birth DATE NOT NULL,
                        gender ENUM('M', 'F', 'Other') NOT NULL,
                        phone VARCHAR(20),
                        email VARCHAR(100),
                        address TEXT,
                        emergency_contact VARCHAR(100),
                        emergency_phone VARCHAR(20),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                'doctors': """
                    CREATE TABLE IF NOT EXISTS doctors (
                        doctor_id INT PRIMARY KEY AUTO_INCREMENT,
                        first_name VARCHAR(50) NOT NULL,
                        last_name VARCHAR(50) NOT NULL,
                        specialization VARCHAR(100) NOT NULL,
                        license_number VARCHAR(50) UNIQUE NOT NULL,
                        phone VARCHAR(20),
                        email VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                'medications': """
                    CREATE TABLE IF NOT EXISTS medications (
                        medication_id INT PRIMARY KEY AUTO_INCREMENT,
                        medication_name VARCHAR(100) NOT NULL,
                        generic_name VARCHAR(100),
                        dosage_form VARCHAR(50),
                        strength VARCHAR(50),
                        manufacturer VARCHAR(100),
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                'prescriptions': """
                    CREATE TABLE IF NOT EXISTS prescriptions (
                        prescription_id INT PRIMARY KEY AUTO_INCREMENT,
                        patient_id INT NOT NULL,
                        doctor_id INT NOT NULL,
                        prescription_date DATE NOT NULL,
                        status ENUM('active', 'completed', 'cancelled') DEFAULT 'active',
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                        FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                    )
                """,
                'prescription_items': """
                    CREATE TABLE IF NOT EXISTS prescription_items (
                        item_id INT PRIMARY KEY AUTO_INCREMENT,
                        prescription_id INT NOT NULL,
                        medication_id INT NOT NULL,
                        dosage VARCHAR(50) NOT NULL,
                        frequency VARCHAR(50) NOT NULL,
                        duration VARCHAR(50) NOT NULL,
                        quantity INT NOT NULL,
                        FOREIGN KEY (prescription_id) REFERENCES prescriptions(prescription_id),
                        FOREIGN KEY (medication_id) REFERENCES medications(medication_id)
                    )
                """,
                'appointments': """
                    CREATE TABLE IF NOT EXISTS appointments (
                        appointment_id INT PRIMARY KEY AUTO_INCREMENT,
                        patient_id INT NOT NULL,
                        doctor_id INT NOT NULL,
                        appointment_date DATETIME NOT NULL,
                        duration_minutes INT DEFAULT 30,
                        status ENUM('scheduled', 'completed', 'cancelled', 'no_show') DEFAULT 'scheduled',
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                        FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                    )
                """,
                'medical_records': """
                    CREATE TABLE IF NOT EXISTS medical_records (
                        record_id INT PRIMARY KEY AUTO_INCREMENT,
                        patient_id INT NOT NULL,
                        doctor_id INT NOT NULL,
                        visit_date DATE NOT NULL,
                        diagnosis TEXT,
                        symptoms TEXT,
                        treatment_plan TEXT,
                        follow_up_date DATE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                        FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                    )
                """,
                'pharmacies': """
                    CREATE TABLE IF NOT EXISTS pharmacies (
                        pharmacy_id INT PRIMARY KEY AUTO_INCREMENT,
                        pharmacy_name VARCHAR(100) NOT NULL,
                        address TEXT NOT NULL,
                        phone VARCHAR(20),
                        email VARCHAR(100),
                        license_number VARCHAR(50) UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                'inventory': """
                    CREATE TABLE IF NOT EXISTS inventory (
                        inventory_id INT PRIMARY KEY AUTO_INCREMENT,
                        pharmacy_id INT NOT NULL,
                        medication_id INT NOT NULL,
                        quantity_in_stock INT DEFAULT 0,
                        reorder_level INT DEFAULT 10,
                        last_restocked DATE,
                        expiry_date DATE,
                        FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(pharmacy_id),
                        FOREIGN KEY (medication_id) REFERENCES medications(medication_id)
                    )
                """,
                'insurance': """
                    CREATE TABLE IF NOT EXISTS insurance (
                        insurance_id INT PRIMARY KEY AUTO_INCREMENT,
                        patient_id INT NOT NULL,
                        insurance_provider VARCHAR(100) NOT NULL,
                        policy_number VARCHAR(50) NOT NULL,
                        coverage_type VARCHAR(50),
                        effective_date DATE,
                        expiry_date DATE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                    )
                """
            }
            
            # Create all tables
            for table_name, create_sql in tables.items():
                cursor.execute(create_sql)
                print(f"SUCCESS: Created table: {table_name}")
            
            # Insert sample data
            self.insert_pharma_sample_data(cursor)
            
            connection.commit()
            cursor.close()
            connection.close()
            
            print("SUCCESS: Pharma database setup completed")
            return True
            
        except Exception as e:
            print(f"ERROR: Pharma database setup failed: {str(e)}")
            return False
    
    def insert_pharma_sample_data(self, cursor):
        """Insert sample data into pharma tables"""
        try:
            # Insert doctors
            doctors_data = [
                ('Dr. Sarah', 'Johnson', 'Cardiology', 'CARD001'),
                ('Dr. Michael', 'Brown', 'Neurology', 'NEURO001'),
                ('Dr. Emily', 'Davis', 'Pediatrics', 'PED001'),
                ('Dr. David', 'Wilson', 'Orthopedics', 'ORTHO001'),
                ('Dr. Lisa', 'Garcia', 'Dermatology', 'DERM001')
            ]
            cursor.executemany(
                "INSERT INTO doctors (first_name, last_name, specialization, license_number) VALUES (%s, %s, %s, %s)",
                doctors_data
            )
            
            # Insert patients
            patients_data = [
                ('John', 'Smith', '1985-03-15', 'M', '555-1001', 'john.smith@email.com', '123 Health St', 'Jane Smith', '555-1002'),
                ('Mary', 'Johnson', '1990-07-22', 'F', '555-1003', 'mary.johnson@email.com', '456 Wellness Ave', 'Bob Johnson', '555-1004'),
                ('Robert', 'Brown', '1978-11-08', 'M', '555-1005', 'robert.brown@email.com', '789 Care Rd', 'Susan Brown', '555-1006'),
                ('Jennifer', 'Davis', '1992-05-30', 'F', '555-1007', 'jennifer.davis@email.com', '321 Medical Blvd', 'Tom Davis', '555-1008'),
                ('William', 'Wilson', '1988-09-12', 'M', '555-1009', 'william.wilson@email.com', '654 Treatment St', 'Linda Wilson', '555-1010')
            ]
            cursor.executemany(
                "INSERT INTO patients (first_name, last_name, date_of_birth, gender, phone, email, address, emergency_contact, emergency_phone) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                patients_data
            )
            
            # Insert medications
            medications_data = [
                ('Lisinopril', 'Lisinopril', 'Tablet', '10mg', 'Generic Pharma', 'ACE inhibitor for blood pressure'),
                ('Metformin', 'Metformin', 'Tablet', '500mg', 'Diabetes Corp', 'Diabetes medication'),
                ('Atorvastatin', 'Atorvastatin', 'Tablet', '20mg', 'Heart Health Inc', 'Cholesterol lowering medication'),
                ('Omeprazole', 'Omeprazole', 'Capsule', '20mg', 'Digestive Care', 'Proton pump inhibitor'),
                ('Amoxicillin', 'Amoxicillin', 'Capsule', '500mg', 'Antibiotic Labs', 'Antibiotic medication')
            ]
            cursor.executemany(
                "INSERT INTO medications (medication_name, generic_name, dosage_form, strength, manufacturer, description) VALUES (%s, %s, %s, %s, %s, %s)",
                medications_data
            )
            
            # Insert prescriptions
            prescriptions_data = [
                (1, 1, '2024-01-15', 'active', 'Regular blood pressure monitoring required'),
                (2, 2, '2024-01-20', 'active', 'Monitor blood sugar levels'),
                (3, 1, '2024-01-25', 'completed', 'Treatment completed successfully'),
                (4, 3, '2024-02-01', 'active', 'Regular check-ups needed'),
                (5, 4, '2024-02-05', 'active', 'Follow dietary restrictions')
            ]
            cursor.executemany(
                "INSERT INTO prescriptions (patient_id, doctor_id, prescription_date, status, notes) VALUES (%s, %s, %s, %s, %s)",
                prescriptions_data
            )
            
            print("SUCCESS: Sample data inserted into pharma tables")
            
        except Exception as e:
            print(f"ERROR: Sample data insertion failed: {str(e)}")

def main():
    """Main function to setup test databases"""
    print("Setting up test databases for SQL AI Agent POC...")
    
    setup = TestDatabaseSetup()
    
    # Create databases
    if not setup.create_databases():
        print("ERROR: Failed to create databases")
        return
    
    # Setup e-commerce database
    if not setup.setup_ecommerce_database():
        print("ERROR: Failed to setup e-commerce database")
        return
    
    # Setup pharma database
    if not setup.setup_pharma_database():
        print("ERROR: Failed to setup pharma database")
        return
    
    print("\nSUCCESS: All test databases setup completed successfully!")
    print("\nDatabase Summary:")
    print("   - ecommerce_test: 10 tables (customers, products, orders, etc.)")
    print("   - pharma_test: 10 tables (patients, doctors, medications, etc.)")
    print("\nConnection strings:")
    print("   - E-commerce: mysql+pymysql://root:Sandhya%40332@localhost:3306/ecommerce_test")
    print("   - Pharma: mysql+pymysql://root:Sandhya%40332@localhost:3306/pharma_test")

if __name__ == "__main__":
    main()
