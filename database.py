from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL koneksi MySQL dengan PyMySQL
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:PasswordBaru123!@localhost:3306/image_db"

# Membuat engine untuk menghubungkan ke database
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Membuat session maker untuk berinteraksi dengan database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class untuk model-model SQLAlchemy
Base = declarative_base()

# Fungsi untuk mendapatkan sesi (session) dari database
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
