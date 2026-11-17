from pathlib import Path
import os

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = os.environ.get("VERCEL") == "1"
DATA_DIR = Path(
    os.environ.get("CIVICFIX_DATA_DIR")
    or ("/tmp/civicfix-ai" if IS_VERCEL else BASE_DIR / "data")
)
UPLOADS_DIR = DATA_DIR / "uploads"
GUIDELINES_DIR = UPLOADS_DIR / "guidelines"
COMPLAINT_IMAGES_DIR = UPLOADS_DIR / "complaints"
FAISS_DIR = DATA_DIR / "faiss_index"

# Create directories if not existing
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
GUIDELINES_DIR.mkdir(parents=True, exist_ok=True)
COMPLAINT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
FAISS_DIR.mkdir(parents=True, exist_ok=True)

# Database
database_url = os.environ.get("DATABASE_URL")
if IS_VERCEL:
    if not database_url or not database_url.startswith(
        ("postgres://", "postgresql://", "postgresql+psycopg://")
    ):
        raise RuntimeError(
            "Vercel requires a persistent PostgreSQL DATABASE_URL. "
            "Configure a PostgreSQL connection string in the Vercel project settings."
        )
elif not database_url:
    database_url = f"sqlite:///{DATA_DIR / 'civicfix.db'}"

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

DATABASE_URL = database_url

# 5 Strict Categories
CATEGORIES = [
    "Road Damage",
    "Drainage Overflow",
    "Garbage Accumulation",
    "Streetlight Failure",
    "Water Leakage"
]

# Rule-based Department Mapping
CATEGORY_DEPARTMENT_MAP = {
    "Road Damage": {
        "name": "Road Maintenance Authority",
        "jurisdiction": "Responsible for municipal and state road repairs, pothole filling, and pavement upkeep in designated ward sectors."
    },
    "Drainage Overflow": {
        "name": "Drainage / Sanitation Department",
        "jurisdiction": "Oversees storm-water drainage networks, sewer line desilting, manhole clearing, and flood prevention."
    },
    "Garbage Accumulation": {
        "name": "Sanitation Department",
        "jurisdiction": "Handles solid waste management, door-to-door garbage collection, community dustbins, and street cleanliness."
    },
    "Streetlight Failure": {
        "name": "Electrical Maintenance Department",
        "jurisdiction": "Maintains municipal public lighting infrastructure, street lamps, timer switches, and electrical feeder pillars."
    },
    "Water Leakage": {
        "name": "Water Supply Department",
        "jurisdiction": "Manages drinking water distribution pipelines, main valve networks, pressure regulation, and emergency leak repairs."
    }
}

# Department default contacts for letter & display
DEFAULT_DEPARTMENTS = [
    {
        "name": "Road Maintenance Authority",
        "code": "RMA",
        "contact_email": "roads@civicfix.local",
        "phone": "1800-11-ROAD (7623)",
        "jurisdiction_notes": "Municipal roads, footpaths, bridges, and express corridors within city limits."
    },
    {
        "name": "Drainage / Sanitation Department",
        "code": "DSD",
        "contact_email": "drainage@civicfix.local",
        "phone": "1800-11-DRAIN (3724)",
        "jurisdiction_notes": "Storm water drains, primary & secondary sewer lines, and desilting operations."
    },
    {
        "name": "Sanitation Department",
        "code": "SND",
        "contact_email": "sanitation@civicfix.local",
        "phone": "1800-11-WASTE (9278)",
        "jurisdiction_notes": "Daily municipal waste collection, dumping yards, and commercial zone sanitization."
    },
    {
        "name": "Electrical Maintenance Department",
        "code": "EMD",
        "contact_email": "electric@civicfix.local",
        "phone": "1800-11-LIGHT (5444)",
        "jurisdiction_notes": "Urban street lighting, LED fixtures, solar lights, and transformer junction boxes."
    },
    {
        "name": "Water Supply Department",
        "code": "WSD",
        "contact_email": "watersupply@civicfix.local",
        "phone": "1800-11-WATER (9283)",
        "jurisdiction_notes": "Public water distribution, pipeline ruptures, community public taps, and booster pumps."
    }
]

# Classification Keywords
CATEGORY_KEYWORDS = {
    "Road Damage": [
        "pothole", "potholes", "road", "roads", "asphalt", "tar", "crater", "caved", "cave-in",
        "divider", "pavement", "footpath", "curb", "bump", "speedbreaker", "resurfacing", "broken road"
    ],
    "Drainage Overflow": [
        "drain", "drainage", "sewer", "sewage", "manhole", "overflow", "overflowing", "gutter",
        "choked", "blocked drain", "stagnant water", "backflow", "foul smell", "wastewater", "sludge"
    ],
    "Garbage Accumulation": [
        "garbage", "trash", "waste", "rubbish", "dump", "dumping", "litter", "debris",
        "dustbin", "uncollected", "filth", "rotting", "plastic waste", "refuse", "stench"
    ],
    "Streetlight Failure": [
        "streetlight", "street light", "streetlights", "lamp", "lamppost", "dark street",
        "no light", "blackout", "bulb", "flickering", "pole", "wiring", "electrical post"
    ],
    "Water Leakage": [
        "water leak", "leakage", "pipeline", "pipe burst", "burst pipe", "pipe leaking",
        "water gushing", "wasted water", "drinking water", "main line", "broken tap", "water supply"
    ]
}

JURISDICTION_DISCLAIMER = (
    "Recommendations are rule-based and subject to verification by your local municipal corporation or ward authority jurisdiction."
)
