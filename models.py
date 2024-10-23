from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class CrawlResult(Base):
    __tablename__ = 'crawl_results'

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    parent_url = Column(String)
    status_code = Column(Integer)
    content_size = Column(Integer)
    title = Column(String)
    crawled_at = Column(DateTime, default=datetime.utcnow)
    statistics = Column(JSON)

# Add more models here as needed
