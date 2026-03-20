from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base() # User DB
BaseMarket = declarative_base() # Market DB (Timescale)
