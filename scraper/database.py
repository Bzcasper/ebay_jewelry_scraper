# scraper/database.py

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from datetime import datetime
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class Item(Base):
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    url = Column(String, unique=True, nullable=False)
    image_url = Column(String, nullable=True)
    image_path = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    shipping = Column(String, nullable=True)
    seller = Column(String, nullable=True)
    location = Column(String, nullable=True)
    category = Column(String, nullable=True)
    subcategory = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Database:
    def __init__(self, db_url=DATABASE_URL):
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_item(self, item_data: dict) -> Optional[Item]:
        session = self.Session()
        try:
            # Check if item already exists
            existing_item = session.query(Item).filter_by(url=item_data['url']).first()
            if existing_item:
                logger.info(f"Item already exists in database: {item_data['url']}")
                return None  # Item already exists

            item = Item(
                title=item_data['title'],
                price=float(item_data['price']),
                url=item_data['url'],
                image_url=item_data.get('image_url'),
                image_path=item_data.get('image_path'),
                condition=item_data.get('condition'),
                shipping=item_data.get('shipping'),
                seller=item_data.get('seller'),
                location=item_data.get('location'),
                category=item_data.get('category'),
                subcategory=item_data.get('subcategory')
            )
            session.add(item)
            session.commit()
            logger.info(f"Saved item to database: {item.title}")
            return item
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving item to database: {e}")
            return None
        finally:
            session.close()

    def get_item_count(self) -> dict:
        session = self.Session()
        try:
            # Count items per category and subcategory
            counts = session.query(Item.category, Item.subcategory, func.count(Item.id)).group_by(Item.category, Item.subcategory).all()

            # Convert to dictionary
            stats = {}
            for category, subcategory, count in counts:
                if category not in stats:
                    stats[category] = {}
                stats[category][subcategory] = count

            return stats
        except Exception as e:
            logger.error(f"Error getting item count: {e}")
            return {'total_items': 0}
        finally:
            session.close()

    def get_recent_items(self, limit=10, category=None, subcategory=None) -> list:
        session = self.Session()
        try:
            query = session.query(Item).order_by(Item.created_at.desc())
            if category:
                query = query.filter_by(category=category)
            if subcategory:
                query = query.filter_by(subcategory=subcategory)
            items = query.limit(limit).all()
            return items
        except Exception as e:
            logger.error(f"Error getting recent items: {e}")
            return []
        finally:
            session.close()

# Initialize the database instance
db = Database()
