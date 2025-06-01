from sqlalchemy.orm import Session
from models import Product

def get_product_by_name(db: Session, name: str):
    return db.query(Product).filter(Product.name == name).first()
